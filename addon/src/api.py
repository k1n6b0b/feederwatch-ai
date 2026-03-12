"""
aiohttp REST + SSE API for FeederWatch AI.

All routes prefixed /api/v1/. Static frontend served from /.
Security headers applied to all responses — HA Ingress compatible.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import tempfile
from collections.abc import AsyncGenerator
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import aiohttp
from aiohttp import web
from pydantic import BaseModel, ValidationError, field_validator

from .config import Config
from .supervisor import discover_frigate_url, discover_mqtt
from .db import (
    delete_detection,
    get_all_species,
    get_daily_detections,
    get_daily_summary,
    get_db_size_bytes,
    get_detection_by_id,
    get_recent_detections,
    get_seasonal_activity,
    get_species_detail,
    get_species_detections,
    get_species_phenology,
    get_total_detection_count,
    get_weekly_heatmap,
    reclassify_detection,
    upsert_species,
)

_LOGGER = logging.getLogger(__name__)

APP_START_TIME = datetime.now(timezone.utc)

# Discovery cache — re-query Supervisor at most once per 60s
_discovery_cache: dict | None = None
_discovery_cache_time: float = 0.0
_DISCOVERY_TTL = 60.0

# ---------------------------------------------------------------------------
# Security middleware — HA Ingress compatible
# ---------------------------------------------------------------------------

@web.middleware
async def security_headers_middleware(request: web.Request, handler: Any) -> web.Response:
    response = await handler(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"  # Must NOT be DENY — HA uses iframe
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # needed for React inline chunks
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"  # Must NOT be 'none' — HA ingress frames us
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Rate limiting middleware (by Ingress session, not IP)
# ---------------------------------------------------------------------------

_rate_limit_counters: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX = 200


@web.middleware
async def rate_limit_middleware(request: web.Request, handler: Any) -> web.Response:
    # Use remote IP as the rate-limit key — X-Ingress-Path is user-forgeable
    key = request.remote or "default"
    now = asyncio.get_event_loop().time()

    window = _rate_limit_counters.setdefault(key, [])
    # Prune entries outside window
    _rate_limit_counters[key] = [t for t in window if now - t < RATE_LIMIT_WINDOW]
    _rate_limit_counters[key].append(now)

    if len(_rate_limit_counters[key]) > RATE_LIMIT_MAX:
        raise web.HTTPTooManyRequests(reason="Rate limit exceeded")

    return await handler(request)


# ---------------------------------------------------------------------------
# Input validation models
# ---------------------------------------------------------------------------

class PaginationParams(BaseModel):
    limit: int = 20
    offset: int = 0
    after_id: int | None = None

    @field_validator("limit")
    @classmethod
    def cap_limit(cls, v: int) -> int:
        return min(max(1, v), 100)

    @field_validator("offset")
    @classmethod
    def non_negative_offset(cls, v: int) -> int:
        return max(0, v)


class DateParam(BaseModel):
    date: str

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        datetime.strptime(v, "%Y-%m-%d")
        return v


class ThresholdParam(BaseModel):
    threshold: float

    @field_validator("threshold")
    @classmethod
    def valid_threshold(cls, v: float) -> float:
        if not 0.1 <= v <= 1.0:
            raise ValueError("threshold must be between 0.1 and 1.0")
        return round(v, 2)


class ReclassifyBody(BaseModel):
    scientific_name: str
    common_name: str

    @field_validator("scientific_name", "common_name")
    @classmethod
    def non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _json_response(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        status=status,
        content_type="application/json",
        text=json.dumps(data, default=str),
    )


def _parse_pagination(request: web.Request) -> PaginationParams:
    try:
        return PaginationParams(
            limit=int(request.rel_url.query.get("limit", 20)),
            offset=int(request.rel_url.query.get("offset", 0)),
            after_id=request.rel_url.query.get("after_id"),
        )
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid pagination parameters")


def _parse_date(request: web.Request, param: str = "date") -> date:
    raw = request.rel_url.query.get(param, datetime.now(timezone.utc).date().isoformat())
    try:
        DateParam(date=raw)
        return date.fromisoformat(raw)
    except Exception:
        raise web.HTTPBadRequest(reason=f"Invalid date format. Expected YYYY-MM-DD, got: {raw}")


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_status(request: web.Request) -> web.Response:
    global _discovery_cache, _discovery_cache_time

    app = request.app
    config: Config = app["config"]
    mqtt_client = app.get("mqtt_client")
    classifier = app.get("classifier")

    uptime = (datetime.now(timezone.utc) - APP_START_TIME).total_seconds()
    db_path: str = app["db_path"]

    total = await get_total_detection_count(db_path)
    db_size = await get_db_size_bytes(db_path)

    # MQTT connected state — set True only after socket connect + subscribe succeed
    mqtt_connected = getattr(mqtt_client, "_connected", False) if mqtt_client else False

    # Frigate reachability — quick HEAD check
    frigate_reachable = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{config.frigate_url}/api/version",
                timeout=aiohttp.ClientTimeout(total=2),
            ) as resp:
                frigate_reachable = resp.status < 500
    except Exception:
        pass

    model_loaded = classifier.is_loaded if classifier else False
    label_mapper = app.get("label_mapper")
    labels_loaded = label_mapper is not None

    # Auto-discovery via Supervisor — cached for 60s
    import asyncio as _asyncio
    now = _asyncio.get_event_loop().time()
    if _discovery_cache is None or (now - _discovery_cache_time) > _DISCOVERY_TTL:
        mqtt_disc, frigate_disc = await _asyncio.gather(
            discover_mqtt(), discover_frigate_url(), return_exceptions=True
        )
        _discovery_cache = {
            "mqtt": mqtt_disc if isinstance(mqtt_disc, dict) else None,
            "frigate_url": frigate_disc if isinstance(frigate_disc, str) else None,
        }
        _discovery_cache_time = now

    return _json_response({
        "mqtt": {
            "connected": mqtt_connected,
            "host": config.mqtt_host,
            "port": config.mqtt_port,
            "authenticated": config.mqtt_username is not None,
            "error": getattr(mqtt_client, "last_error", None),
            "error_type": getattr(mqtt_client, "error_type", None),
        },
        "frigate": {
            "reachable": frigate_reachable,
            "url": config.frigate_url,
        },
        "model": {
            "loaded": model_loaded,
            "labels_loaded": labels_loaded,
            "path": config.model_path,
            "input_size": 224,
        },
        "database": {
            "ok": True,
            "detections": total,
            "size_bytes": db_size,
        },
        "uptime_seconds": int(uptime),
        "version": "0.1.0",
        "discovery": _discovery_cache,
    })


async def handle_recent_detections(request: web.Request) -> web.Response:
    pagination = _parse_pagination(request)
    db_path: str = request.app["db_path"]
    rows = await get_recent_detections(
        db_path, limit=pagination.limit, after_id=pagination.after_id
    )
    return _json_response(rows)


async def handle_daily_detections(request: web.Request) -> web.Response:
    pagination = _parse_pagination(request)
    target_date = _parse_date(request)
    db_path: str = request.app["db_path"]
    rows = await get_daily_detections(
        db_path, target_date, limit=pagination.limit, offset=pagination.offset
    )
    return _json_response(rows)


async def handle_daily_summary(request: web.Request) -> web.Response:
    target_date = _parse_date(request)
    db_path: str = request.app["db_path"]
    summary = await get_daily_summary(db_path, target_date)
    return _json_response(summary)


async def handle_species_list(request: web.Request) -> web.Response:
    pagination = _parse_pagination(request)
    sort = request.rel_url.query.get("sort", "count")
    if sort not in ("count", "recent", "alpha", "first"):
        raise web.HTTPBadRequest(reason="sort must be one of: count, recent, alpha, first")
    db_path: str = request.app["db_path"]
    rows = await get_all_species(
        db_path, sort=sort, limit=pagination.limit, offset=pagination.offset
    )
    return _json_response(rows)


async def handle_species_detail(request: web.Request) -> web.Response:
    scientific_name = request.match_info["scientific_name"]
    db_path: str = request.app["db_path"]
    detail = await get_species_detail(db_path, scientific_name)
    if detail is None:
        raise web.HTTPNotFound(reason="Species not found")
    return _json_response(detail)


async def handle_species_phenology(request: web.Request) -> web.Response:
    scientific_name = request.match_info["scientific_name"]
    db_path: str = request.app["db_path"]
    data = await get_species_phenology(db_path, scientific_name)
    return _json_response(data)


async def handle_delete_detection(request: web.Request) -> web.Response:
    try:
        detection_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Detection ID must be an integer")
    db_path: str = request.app["db_path"]
    result = await delete_detection(db_path, detection_id)
    if result is None:
        raise web.HTTPNotFound(reason="Detection not found")
    return _json_response(result)


async def handle_reclassify_detection(request: web.Request) -> web.Response:
    try:
        detection_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Detection ID must be an integer")

    try:
        body = await request.json()
        params = ReclassifyBody(**body)
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        reason = str(exc).replace("\n", " ").replace("\r", "")[:200]
        raise web.HTTPBadRequest(reason=f"Invalid request body: {reason}")

    db_path: str = request.app["db_path"]
    await upsert_species(db_path, params.scientific_name, params.common_name)
    updated = await reclassify_detection(
        db_path, detection_id, params.scientific_name, params.common_name
    )
    if not updated:
        raise web.HTTPNotFound(reason="Detection not found")
    return _json_response({
        "reclassified": True,
        "id": detection_id,
        "scientific_name": params.scientific_name,
        "common_name": params.common_name,
    })


async def handle_species_search(request: web.Request) -> web.Response:
    """Search species by common or scientific name. Pure in-memory lookup."""
    from .bird_names import BIRD_NAMES
    q = request.rel_url.query.get("q", "").strip().lower()
    try:
        limit = min(int(request.rel_url.query.get("limit", 20)), 50)
    except ValueError:
        limit = 20

    if not q:
        return _json_response([])

    results = []
    for sci, common in BIRD_NAMES.items():
        if q in common.lower() or q in sci.lower():
            results.append({"scientific_name": sci, "common_name": common})
        if len(results) >= limit:
            break

    return _json_response(results)


async def handle_events_recent(request: web.Request) -> web.Response:
    """Return MQTT ring buffer for connection-status debugging."""
    mqtt_client = request.app.get("mqtt_client")
    if mqtt_client is None:
        return _json_response([])
    return _json_response(mqtt_client.ring_buffer)


async def handle_set_threshold(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        params = ThresholdParam(**body)
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        # Strip newlines — aiohttp rejects reason strings containing \n
        reason = str(exc).replace("\n", " ").replace("\r", "")[:200]
        raise web.HTTPBadRequest(reason=f"Invalid request body: {reason}")
    config: Config = request.app["config"]
    config.classification_threshold = params.threshold
    _LOGGER.info("Threshold updated to %.2f", params.threshold)
    return _json_response({"threshold": params.threshold})


async def handle_snapshot(request: web.Request) -> web.Response:
    """Proxy snapshot — local file first, then Frigate, then placeholder."""
    try:
        detection_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Detection ID must be an integer")

    db_path: str = request.app["db_path"]
    config: Config = request.app["config"]

    detection = await get_detection_by_id(db_path, detection_id)
    if detection is None:
        raise web.HTTPNotFound(reason="Detection not found")

    # Try local snapshot first — validate path is within snapshots directory
    local_path = detection.get("snapshot_path")
    if local_path:
        snapshots_dir = os.path.realpath("/data/snapshots")
        real_path = os.path.realpath(local_path)
        if real_path.startswith(snapshots_dir + os.sep) and os.path.exists(real_path):
            with open(real_path, "rb") as f:
                return web.Response(body=f.read(), content_type="image/jpeg")

    # Fall back to Frigate — URL-encode event ID to prevent path injection
    event_id = quote(str(detection["frigate_event_id"]), safe="")
    frigate_url = f"{config.frigate_url}/api/events/{event_id}/snapshot.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(frigate_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return web.Response(body=data, content_type="image/jpeg")
    except Exception as exc:
        _LOGGER.debug("Frigate snapshot unavailable: %s", exc)

    # Placeholder
    raise web.HTTPNotFound(reason="Snapshot no longer available")


async def handle_detection_clip(request: web.Request) -> web.Response:
    """Proxy Frigate video clip — avoids CORS by serving via our own origin."""
    try:
        detection_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Detection ID must be an integer")

    db_path: str = request.app["db_path"]
    config: Config = request.app["config"]

    detection = await get_detection_by_id(db_path, detection_id)
    if detection is None:
        raise web.HTTPNotFound(reason="Detection not found")

    event_id = quote(str(detection["frigate_event_id"]), safe="")
    clip_url = f"{config.frigate_url}/api/events/{event_id}/clip.mp4"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(clip_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return web.Response(body=data, content_type="video/mp4")
                if resp.status == 404:
                    raise web.HTTPNotFound(reason="Clip not available in Frigate")
    except web.HTTPException:
        raise
    except Exception as exc:
        _LOGGER.debug("Frigate clip unavailable: %s", exc)

    raise web.HTTPNotFound(reason="Clip no longer available")


async def handle_weekly_heatmap(request: web.Request) -> web.Response:
    """Day-of-week × hour heatmap for the last 4 weeks."""
    db_path: str = request.app["db_path"]
    cells = await get_weekly_heatmap(db_path, days=28)
    return _json_response(cells)


async def handle_species_detections(request: web.Request) -> web.Response:
    """Paginated detections for a single species (photo grid)."""
    scientific_name = request.match_info["scientific_name"]
    pagination = _parse_pagination(request)
    db_path: str = request.app["db_path"]
    rows = await get_species_detections(
        db_path, scientific_name, limit=pagination.limit, offset=pagination.offset
    )
    return _json_response(rows)


async def handle_seasonal_activity(request: web.Request) -> web.Response:
    """Weekly species/detection counts for the last 52 weeks (SeasonalChart)."""
    db_path: str = request.app["db_path"]
    data = await get_seasonal_activity(db_path)
    return _json_response(data)


async def handle_export_csv(request: web.Request) -> web.Response:
    import csv
    import io

    db_path: str = request.app["db_path"]
    date_param = request.rel_url.query.get("date")
    if date_param:
        # Validate before use in filename — rejects path separators and injection
        try:
            target_date: date | None = date.fromisoformat(date_param)
        except ValueError:
            raise web.HTTPBadRequest(reason=f"Invalid date format, expected YYYY-MM-DD: {date_param}")
    else:
        target_date = None

    if target_date:
        rows = await get_daily_detections(db_path, target_date, limit=100, offset=0)
        # Paginate all
        all_rows = list(rows)
        offset = 100
        while len(rows) == 100:
            rows = await get_daily_detections(db_path, target_date, limit=100, offset=offset)
            all_rows.extend(rows)
            offset += 100
    else:
        all_rows = []
        after_id = None
        while True:
            batch = await get_recent_detections(db_path, limit=100, after_id=after_id)
            if not batch:
                break
            all_rows.extend(batch)
            after_id = batch[-1]["id"]
            if len(batch) < 100:
                break

    CSV_FIELDS = [
        "id", "frigate_event_id", "scientific_name", "common_name",
        "score", "category_name", "camera_name", "snapshot_path", "detected_at",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    if all_rows:
        writer.writerows(all_rows)

    filename = f"feederwatch_{date_param or 'all'}.csv"
    return web.Response(
        body=output.getvalue().encode(),
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# WAMF migration import
# ---------------------------------------------------------------------------

async def handle_import_wamf(request: web.Request) -> web.Response:
    """Upload a WhosAtMyFeeder speciesid.db and migrate its detections.

    Expects JSON body: {"filename": "speciesid.db", "data": "<base64>"}
    Base64 encoding is used instead of multipart to ensure compatibility with HA Ingress.
    """
    from .migrate_wamf import migrate_wamf

    MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB — speciesid.db is typically < 10 MB

    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Expected JSON body with 'filename' and 'data' fields")

    b64_data = body.get("data")
    if not b64_data:
        raise web.HTTPBadRequest(reason="Missing 'data' field (base64-encoded file contents)")

    try:
        raw_bytes = base64.b64decode(b64_data)
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid base64 in 'data' field")

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise web.HTTPRequestEntityTooLarge(
            reason=f"Upload exceeds {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit"
        )

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="wamf_import_")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(raw_bytes)

        db_path: str = request.app["db_path"]
        result = await migrate_wamf(tmp_path, db_path)
        _LOGGER.info("WAMF import complete: %s", result)
        return _json_response(result)
    except web.HTTPException:
        raise
    except Exception as exc:
        reason = str(exc).replace("\n", " ").replace("\r", "")[:200]
        _LOGGER.error("WAMF import failed: %s", exc)
        raise web.HTTPInternalServerError(reason=f"Import failed: {reason}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# SSE — real-time detection stream
# ---------------------------------------------------------------------------

async def handle_detection_stream(request: web.Request) -> web.StreamResponse:
    """Server-Sent Events endpoint. Pushes new detections in real time."""
    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"  # disable nginx buffering if present
    await response.prepare(request)

    queue: asyncio.Queue = asyncio.Queue()
    sse_subscribers: list[asyncio.Queue] = request.app["sse_subscribers"]
    sse_subscribers.append(queue)

    try:
        # Send a keepalive comment every 15s to prevent proxy timeouts
        async def keepalive() -> None:
            while True:
                await asyncio.sleep(15)
                try:
                    await response.write(b": keepalive\n\n")
                except Exception:
                    break

        ka_task = asyncio.create_task(keepalive())

        while True:
            try:
                detection = await asyncio.wait_for(queue.get(), timeout=30)
                data = json.dumps(detection, default=str)
                await response.write(f"data: {data}\n\n".encode())
            except asyncio.TimeoutError:
                # Client still connected — keepalive task handles pings
                continue
            except (ConnectionResetError, Exception):
                break
    finally:
        ka_task.cancel()
        sse_subscribers.remove(queue)

    return response


async def broadcast_detection(app: web.Application, detection: dict) -> None:
    """Called by mqtt_client when a new detection is saved."""
    subscribers: list[asyncio.Queue] = app.get("sse_subscribers", [])
    for queue in subscribers:
        await queue.put(detection)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    config: Config,
    db_path: str,
    classifier: Any = None,
    mqtt_client: Any = None,
    static_path: str = "/app/frontend/dist",
) -> web.Application:
    app = web.Application(middlewares=[security_headers_middleware, rate_limit_middleware])

    app["config"] = config
    app["db_path"] = db_path
    app["classifier"] = classifier
    app["mqtt_client"] = mqtt_client
    app["sse_subscribers"] = []

    # Routes
    app.router.add_get("/api/v1/status", handle_status)
    # Static detection routes must come before /{id}/... dynamic routes
    app.router.add_get("/api/v1/detections/recent", handle_recent_detections)
    app.router.add_get("/api/v1/detections/daily", handle_daily_detections)
    app.router.add_get("/api/v1/detections/daily/summary", handle_daily_summary)
    app.router.add_get("/api/v1/detections/stream", handle_detection_stream)
    app.router.add_get("/api/v1/detections/weekly-heatmap", handle_weekly_heatmap)
    app.router.add_get("/api/v1/detections/{id}/snapshot", handle_snapshot)
    app.router.add_get("/api/v1/detections/{id}/clip", handle_detection_clip)
    app.router.add_delete("/api/v1/detections/{id}", handle_delete_detection)
    app.router.add_patch("/api/v1/detections/{id}/reclassify", handle_reclassify_detection)
    # Static species routes must come before /{scientific_name} dynamic routes
    app.router.add_get("/api/v1/species/search", handle_species_search)
    app.router.add_get("/api/v1/species/seasonal", handle_seasonal_activity)
    app.router.add_get("/api/v1/species", handle_species_list)
    app.router.add_get("/api/v1/species/{scientific_name}", handle_species_detail)
    app.router.add_get("/api/v1/species/{scientific_name}/phenology", handle_species_phenology)
    app.router.add_get("/api/v1/species/{scientific_name}/detections", handle_species_detections)
    app.router.add_get("/api/v1/events/recent", handle_events_recent)
    app.router.add_post("/api/v1/config/threshold", handle_set_threshold)
    app.router.add_get("/api/v1/export/csv", handle_export_csv)
    app.router.add_post("/api/v1/admin/import-wamf", handle_import_wamf)

    # Serve React SPA — all non-API routes serve index.html
    if os.path.isdir(static_path):
        app.router.add_static("/assets", os.path.join(static_path, "assets"))
        app.router.add_get("/{tail:.*}", _spa_handler(static_path))
    else:
        _LOGGER.warning("Static path not found: %s — frontend will not be served", static_path)

    return app


def _spa_handler(static_path: str):
    index_path = os.path.join(static_path, "index.html")

    async def handler(request: web.Request) -> web.Response:
        if os.path.exists(index_path):
            with open(index_path) as f:
                return web.Response(content_type="text/html", text=f.read())
        raise web.HTTPNotFound()

    return handler
