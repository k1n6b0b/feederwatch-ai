"""
Tests for api.py — all REST routes via aiohttp TestClient.
DB is a real temp file; classifier and mqtt_client are mocked.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.api import create_app
from src.config import Config
from src.db import init_db, insert_detection, upsert_species


def make_config():
    return Config(
        frigate_url="http://frigate:5000",
        mqtt_host="localhost",
        mqtt_port=1883,
    )


@pytest.fixture
async def client(tmp_path, aiohttp_client):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    classifier = MagicMock()
    classifier.is_loaded = True
    mqtt_client = MagicMock()
    mqtt_client._running = True
    mqtt_client.ring_buffer = []

    app = create_app(
        config=make_config(),
        db_path=db_path,
        classifier=classifier,
        mqtt_client=mqtt_client,
        static_path="/nonexistent",
    )
    app["_test_db_path"] = db_path
    return await aiohttp_client(app), db_path


# ---------------------------------------------------------------------------
# /api/v1/status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_200(client):
    c, _ = client
    with patch("src.api.aiohttp.ClientSession"):
        resp = await c.get("/api/v1/status")
    assert resp.status == 200
    data = await resp.json()
    assert "mqtt" in data
    assert "version" in data


# ---------------------------------------------------------------------------
# /api/v1/detections/recent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_detections_empty(client):
    c, _ = client
    resp = await c.get("/api/v1/detections/recent")
    assert resp.status == 200
    data = await resp.json()
    assert data == []


@pytest.mark.asyncio
async def test_recent_detections_returns_data(client):
    c, db_path = client
    await upsert_species(db_path, "Poecile atricapillus", "Black-capped Chickadee")
    await insert_detection(db_path, "evt_001", "Poecile atricapillus", "Black-capped Chickadee", 0.96, "ai_classified", "birdcam")

    resp = await c.get("/api/v1/detections/recent?limit=10")
    assert resp.status == 200
    data = await resp.json()
    assert len(data) == 1
    assert data[0]["common_name"] == "Black-capped Chickadee"


@pytest.mark.asyncio
async def test_recent_detections_limit_capped(client):
    c, _ = client
    # limit=999 should not error — capped at 100 internally
    resp = await c.get("/api/v1/detections/recent?limit=999")
    assert resp.status == 200


# ---------------------------------------------------------------------------
# /api/v1/detections/daily
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_detections_invalid_date(client):
    c, _ = client
    resp = await c.get("/api/v1/detections/daily?date=not-a-date")
    assert resp.status == 400


@pytest.mark.asyncio
async def test_daily_detections_valid_date(client):
    c, _ = client
    resp = await c.get("/api/v1/detections/daily?date=2024-01-15")
    assert resp.status == 200
    assert await resp.json() == []


# ---------------------------------------------------------------------------
# /api/v1/detections/daily/summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_summary(client):
    c, _ = client
    resp = await c.get("/api/v1/detections/daily/summary?date=2024-01-15")
    assert resp.status == 200
    data = await resp.json()
    assert "hourly" in data
    assert len(data["hourly"]) == 24
    assert "species" in data


# ---------------------------------------------------------------------------
# /api/v1/species
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_species_list_empty(client):
    c, _ = client
    resp = await c.get("/api/v1/species")
    assert resp.status == 200
    assert await resp.json() == []


@pytest.mark.asyncio
async def test_species_list_invalid_sort(client):
    c, _ = client
    resp = await c.get("/api/v1/species?sort=invalid")
    assert resp.status == 400


@pytest.mark.asyncio
async def test_species_detail_not_found(client):
    c, _ = client
    resp = await c.get("/api/v1/species/Unknown%20species")
    assert resp.status == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/detections/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_detection(client):
    c, db_path = client
    await upsert_species(db_path, "Poecile atricapillus", "Black-capped Chickadee")
    det_id = await insert_detection(db_path, "evt_del", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")

    resp = await c.delete(f"/api/v1/detections/{det_id}")
    assert resp.status == 200
    data = await resp.json()
    assert data["deleted"] is True
    assert data["id"] == det_id


@pytest.mark.asyncio
async def test_delete_detection_not_found(client):
    c, _ = client
    resp = await c.delete("/api/v1/detections/99999")
    assert resp.status == 404


@pytest.mark.asyncio
async def test_delete_detection_invalid_id(client):
    c, _ = client
    resp = await c.delete("/api/v1/detections/not-an-int")
    assert resp.status == 400


# ---------------------------------------------------------------------------
# /api/v1/config/threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_threshold_valid(client):
    c, _ = client
    resp = await c.post("/api/v1/config/threshold", json={"threshold": 0.85})
    assert resp.status == 200
    data = await resp.json()
    assert data["threshold"] == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_set_threshold_out_of_range(client):
    c, _ = client
    resp = await c.post("/api/v1/config/threshold", json={"threshold": 1.5})
    assert resp.status == 400


@pytest.mark.asyncio
async def test_set_threshold_missing_field(client):
    c, _ = client
    resp = await c.post("/api/v1/config/threshold", json={})
    assert resp.status == 400


# ---------------------------------------------------------------------------
# /api/v1/events/recent (ring buffer)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_events_recent_empty(client):
    c, _ = client
    resp = await c.get("/api/v1/events/recent")
    assert resp.status == 200
    assert await resp.json() == []


# ---------------------------------------------------------------------------
# /api/v1/export/csv
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_csv_empty(client):
    c, _ = client
    resp = await c.get("/api/v1/export/csv")
    assert resp.status == 200
    assert resp.content_type == "text/csv"


@pytest.mark.asyncio
async def test_export_csv_with_date(client):
    c, _ = client
    resp = await c.get("/api/v1/export/csv?date=2024-01-15")
    assert resp.status == 200


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_routes_have_security_headers(client):
    c, _ = client
    routes = [
        "/api/v1/status",
        "/api/v1/detections/recent",
        "/api/v1/species",
        "/api/v1/events/recent",
    ]
    with patch("src.api.aiohttp.ClientSession"):
        for route in routes:
            resp = await c.get(route)
            assert resp.headers.get("X-Content-Type-Options") == "nosniff", f"Missing header on {route}"
            assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN", f"Wrong X-Frame-Options on {route}"
