"""
MQTT client for FeederWatch AI.

Consumes Frigate events, classifies birds, stores detections.
Single async context manager — no threading, no fork-safety issues.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp
from pydantic import BaseModel, ValidationError

from .classifier import BirdClassifier, LabelMapper
from .config import Config
from .db import (
    detection_exists,
    insert_detection,
    is_first_ever_species,
    upsert_species,
)

_LOGGER = logging.getLogger(__name__)

# Ring buffer capacity for MQTT event debug log
RING_BUFFER_SIZE = 50


# ---------------------------------------------------------------------------
# Pydantic models — validate Frigate MQTT payloads
# ---------------------------------------------------------------------------

class FrigateEventAfter(BaseModel):
    camera: str
    label: str
    sub_label: str | None = None
    score: float | None = None
    snapshot: dict | None = None


class FrigateEventPayload(BaseModel):
    type: str  # "new" | "update" | "end"
    before: dict[str, Any] | None = None
    after: FrigateEventAfter | None = None


# ---------------------------------------------------------------------------
# Ring buffer entry
# ---------------------------------------------------------------------------

@dataclass
class RingBufferEntry:
    timestamp: str
    camera: str
    frigate_event_id: str
    our_score: float | None
    threshold: float
    action: str          # "saved_ai", "saved_frigate", "below_threshold", "no_bird", "error"
    raw_payload: dict


# ---------------------------------------------------------------------------
# Presence tracking
# ---------------------------------------------------------------------------

@dataclass
class PresenceState:
    active_events: dict[str, str] = field(default_factory=dict)  # event_id → scientific_name
    # scientific_name → last event timestamp
    species_last_seen: dict[str, datetime] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# MQTT runner
# ---------------------------------------------------------------------------

class MQTTClient:
    def __init__(
        self,
        config: Config,
        classifier: BirdClassifier,
        label_mapper: LabelMapper,
        db_path: str,
        on_detection_callback: Any = None,
        on_presence_callback: Any = None,
    ) -> None:
        self._config = config
        self._classifier = classifier
        self._label_mapper = label_mapper
        self._db_path = db_path
        self._on_detection = on_detection_callback
        self._on_presence = on_presence_callback
        self._ring_buffer: deque[RingBufferEntry] = deque(maxlen=RING_BUFFER_SIZE)
        self._presence = PresenceState()
        self._running = False
        self._connected = False
        self._last_error: str | None = None
        self._error_type: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def error_type(self) -> str | None:
        return self._error_type

    @property
    def ring_buffer(self) -> list[dict]:
        return [
            {
                "timestamp": e.timestamp,
                "camera": e.camera,
                "frigate_event_id": e.frigate_event_id,
                "our_score": e.our_score,
                "threshold": e.threshold,
                "action": e.action,
                "raw_payload": e.raw_payload,
            }
            for e in reversed(self._ring_buffer)
        ]

    async def run(self) -> None:
        import aiomqtt  # type: ignore[import]

        self._running = True
        tls_context = ssl.create_default_context() if self._config.mqtt_use_tls else None

        connect_kwargs: dict[str, Any] = {
            "hostname": self._config.mqtt_host,
            "port": self._config.mqtt_port,
            "tls_context": tls_context,
        }
        if self._config.mqtt_username:
            connect_kwargs["username"] = self._config.mqtt_username
        if self._config.mqtt_password:
            connect_kwargs["password"] = self._config.mqtt_password

        topic = f"{self._config.frigate_topic}/events"
        _LOGGER.info(
            "Connecting to MQTT %s:%d (%s) topic=%s",
            self._config.mqtt_host,
            self._config.mqtt_port,
            "authenticated" if self._config.mqtt_username else "anonymous",
            topic,
        )

        async with aiomqtt.Client(**connect_kwargs) as client:
            await client.subscribe(topic)
            self._connected = True
            self._last_error = None
            self._error_type = None
            _LOGGER.info("Subscribed to %s", topic)
            try:
                async for message in client.messages:
                    if not self._running:
                        break
                    asyncio.create_task(
                        self._handle_message(message, client),
                        name=f"handle_mqtt_{id(message)}",
                    )
            finally:
                self._connected = False

    def stop(self) -> None:
        self._running = False

    async def _handle_message(self, message: Any, client: Any) -> None:
        raw_payload: dict = {}
        camera = "unknown"
        frigate_event_id = "unknown"

        try:
            raw_str = message.payload.decode("utf-8")
            raw_payload = json.loads(raw_str)
        except Exception as exc:
            _LOGGER.warning("Failed to decode MQTT payload: %s", exc)
            self._push_ring(camera, frigate_event_id, None, "error", raw_payload)
            return

        # Extract event ID from topic: frigate/events → split
        topic_parts = str(message.topic).split("/")
        # Frigate event IDs are in the payload, not the topic
        frigate_event_id = raw_payload.get("after", {}).get("id") or raw_payload.get("before", {}).get("id", "unknown")

        try:
            event = FrigateEventPayload.model_validate(raw_payload)
        except ValidationError as exc:
            _LOGGER.warning("Invalid Frigate event payload: %s", exc)
            self._push_ring(camera, frigate_event_id, None, "error", raw_payload)
            return

        # Only process "new" and "update" events; "end" updates presence
        if event.type == "end":
            await self._handle_event_end(frigate_event_id, raw_payload)
            return

        if event.type not in ("new", "update"):
            return

        after = event.after
        if not after:
            return

        camera = after.camera

        # Only process cameras we're configured to monitor
        if self._config.camera_names and camera not in self._config.camera_names:
            return

        # Only process bird detections
        if after.label != "bird":
            return

        # Skip duplicates
        if await detection_exists(self._db_path, frigate_event_id):
            return

        await self._classify_and_store(
            frigate_event_id=frigate_event_id,
            camera=camera,
            sub_label=after.sub_label,
            raw_payload=raw_payload,
            client=client,
        )

    async def _classify_and_store(
        self,
        frigate_event_id: str,
        camera: str,
        sub_label: str | None,
        raw_payload: dict,
        client: Any,
    ) -> None:
        threshold = self._config.classification_threshold

        # Fetch snapshot from Frigate
        snapshot_bytes = await self._fetch_snapshot(frigate_event_id)
        if snapshot_bytes is None:
            self._push_ring(camera, frigate_event_id, None, "error", raw_payload)
            return

        # Run our classifier
        our_score: float | None = None
        scientific_name: str | None = None
        category = "below_threshold"

        try:
            raw_results = await self._classifier.classify(snapshot_bytes)
            mapped = self._label_mapper.map_results(raw_results)
            if mapped:
                top = mapped[0]
                our_score = top["score"]
                if our_score >= threshold:
                    scientific_name = top["scientific_name"]
                    category = "ai_classified"
        except Exception as exc:
            _LOGGER.error("Classification error for event %s: %s", frigate_event_id, exc)
            self._push_ring(camera, frigate_event_id, our_score, "error", raw_payload)
            return

        # Frigate sublabel fallback
        if scientific_name is None and sub_label:
            scientific_name = sub_label
            category = "frigate_classified"
            our_score = None
            _LOGGER.debug("Using Frigate sublabel fallback: %s", sub_label)

        if scientific_name is None:
            action = "below_threshold" if our_score is not None else "no_bird"
            _LOGGER.debug(
                "No detection for event %s (score=%s threshold=%s)",
                frigate_event_id, our_score, threshold,
            )
            self._push_ring(camera, frigate_event_id, our_score, action, raw_payload)
            return

        # Look up common name from baked-in dict (no DB round-trip)
        common_name = self._label_mapper.get_common_name(scientific_name)

        # Check if first ever before insert
        first_ever = await is_first_ever_species(self._db_path, scientific_name)

        # Save snapshot locally if configured
        snapshot_path: str | None = None
        if self._config.store_snapshots:
            snapshot_path = await self._save_snapshot(frigate_event_id, snapshot_bytes)

        # Ensure species exists
        await upsert_species(self._db_path, scientific_name, common_name)

        # Insert detection
        detection_id = await insert_detection(
            db_path=self._db_path,
            frigate_event_id=frigate_event_id,
            scientific_name=scientific_name,
            common_name=common_name,
            score=our_score,
            category_name=category,
            camera_name=camera,
            snapshot_path=snapshot_path,
        )

        detection = {
            "id": detection_id,
            "frigate_event_id": frigate_event_id,
            "scientific_name": scientific_name,
            "common_name": common_name,
            "score": our_score,
            "category_name": category,
            "camera_name": camera,
            "snapshot_path": snapshot_path,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "is_first_ever": first_ever,
        }

        _LOGGER.info(
            "Detection saved: %s (%.0f%%) camera=%s event=%s",
            common_name,
            (our_score or 0) * 100,
            camera,
            frigate_event_id,
        )

        # Update presence state
        self._presence.active_events[frigate_event_id] = scientific_name
        self._presence.species_last_seen[scientific_name] = datetime.now(timezone.utc)

        # Publish MQTT (WAMF compat + new topics)
        await self._publish_detection(client, detection, first_ever)

        # Notify callback (for SSE broadcast)
        if self._on_detection:
            await self._on_detection(detection)

        if self._on_presence:
            await self._on_presence(scientific_name, True)

        action = f"saved_{category.split('_')[0]}"
        self._push_ring(camera, frigate_event_id, our_score, action, raw_payload)

    async def _handle_event_end(self, frigate_event_id: str, raw_payload: dict) -> None:
        scientific_name = self._presence.active_events.pop(frigate_event_id, None)
        if scientific_name and self._on_presence:
            # Only mark absent if no other active event for this species
            still_active = any(
                sn == scientific_name
                for sn in self._presence.active_events.values()
            )
            if not still_active:
                await self._on_presence(scientific_name, False)

    async def _fetch_snapshot(self, frigate_event_id: str) -> bytes | None:
        url = f"{self._config.frigate_url}/api/events/{frigate_event_id}/snapshot.jpg"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    _LOGGER.warning("Snapshot fetch failed: %s %s", resp.status, url)
                    return None
        except Exception as exc:
            _LOGGER.warning("Snapshot fetch error for %s: %s", frigate_event_id, exc)
            return None

    async def _save_snapshot(self, frigate_event_id: str, data: bytes) -> str | None:
        import os
        import re
        snapshots_dir = "/data/snapshots"
        os.makedirs(snapshots_dir, exist_ok=True)
        # Validate event ID is safe for use as a filename (Frigate uses UUID format)
        if not re.match(r'^[a-zA-Z0-9_\-]+$', frigate_event_id):
            _LOGGER.warning("Rejecting snapshot with unsafe event ID: %r", frigate_event_id)
            return None
        path = f"{snapshots_dir}/{frigate_event_id}.jpg"
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _write_file, path, data)
            return path
        except Exception as exc:
            _LOGGER.warning("Failed to save snapshot %s: %s", path, exc)
            return None

    async def _publish_detection(
        self, client: Any, detection: dict, first_ever: bool
    ) -> None:
        common_name = detection["common_name"]
        scientific_name = detection["scientific_name"]
        score = detection.get("score") or 0

        try:
            # WAMF backward-compat topics
            await client.publish("whosatmyfeeder/detections", common_name, retain=False)

            if first_ever:
                payload = json.dumps({
                    "common_name": common_name,
                    "scientific_name": scientific_name,
                    "score": score,
                    "camera": detection["camera_name"],
                    "frigate_event": detection["frigate_event_id"],
                })
                await client.publish("whosatmyfeeder/new_species", payload, retain=True)
                await client.publish("whosatmyfeeder/new_species/common_name", common_name, retain=True)
                await client.publish("whosatmyfeeder/new_species/scientific_name", scientific_name, retain=True)
                await client.publish("whosatmyfeeder/new_species/score", str(score), retain=True)
                await client.publish("whosatmyfeeder/new_species/camera", detection["camera_name"], retain=True)
                await client.publish("whosatmyfeeder/new_species/frigate_event", detection["frigate_event_id"], retain=True)

            # New FeederWatch AI topics
            await client.publish(
                "feederwatch_ai/detection",
                json.dumps(detection),
                retain=False,
            )
        except Exception as exc:
            _LOGGER.warning("MQTT publish error: %s", exc)

    def _push_ring(
        self,
        camera: str,
        frigate_event_id: str,
        our_score: float | None,
        action: str,
        raw_payload: dict,
    ) -> None:
        self._ring_buffer.append(
            RingBufferEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                camera=camera,
                frigate_event_id=frigate_event_id,
                our_score=our_score,
                threshold=self._config.classification_threshold,
                action=action,
                raw_payload=raw_payload,
            )
        )


def _write_file(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
