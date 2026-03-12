"""
Tests for connection-status states.

Validates that /api/v1/status returns the correct shape to drive
the StatusChip component through all 3 states: connected, degraded, error.

MQTT password must never appear in any status response.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.api import create_app
from src.config import Config


def make_config(**overrides) -> Config:
    defaults = dict(
        frigate_url="http://frigate:5000",
        mqtt_host="homeassistant.local",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        mqtt_use_tls=False,
        camera_names=["birdcam"],
        classification_threshold=0.7,
        model_path="/data/model.tflite",
    )
    defaults.update(overrides)
    return Config(**defaults)


def make_app(tmp_path, mqtt_running=True, model_loaded=True, frigate_ok=True):
    db_path = str(tmp_path / "test.db")

    classifier = MagicMock()
    classifier.is_loaded = model_loaded

    mqtt_client = MagicMock()
    mqtt_client._running = mqtt_running
    mqtt_client.ring_buffer = []

    config = make_config()
    app = create_app(
        config=config,
        db_path=db_path,
        classifier=classifier,
        mqtt_client=mqtt_client,
        static_path="/nonexistent",
    )
    return app, db_path


@pytest.mark.asyncio
async def test_status_all_healthy(tmp_path, aiohttp_client):
    app, db_path = make_app(tmp_path, mqtt_running=True, model_loaded=True, frigate_ok=True)

    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession") as mock_session:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value.get.return_value = mock_resp

        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        assert resp.status == 200
        data = await resp.json()

    assert data["mqtt"]["connected"] is True
    assert data["model"]["loaded"] is True
    assert data["database"]["ok"] is True
    # All healthy → frontend can derive chip state = "connected"
    assert all([
        data["mqtt"]["connected"],
        data["model"]["loaded"],
        data["database"]["ok"],
    ])


@pytest.mark.asyncio
async def test_status_mqtt_disconnected(tmp_path, aiohttp_client):
    app, db_path = make_app(tmp_path, mqtt_running=False, model_loaded=True)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    # MQTT down → degraded (not error — model and DB still ok)
    assert data["mqtt"]["connected"] is False
    assert data["model"]["loaded"] is True
    assert data["database"]["ok"] is True


@pytest.mark.asyncio
async def test_status_model_not_loaded_is_error(tmp_path, aiohttp_client):
    app, db_path = make_app(tmp_path, mqtt_running=True, model_loaded=False)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    # Model not loaded → error state
    assert data["model"]["loaded"] is False


@pytest.mark.asyncio
async def test_status_no_password_in_response(tmp_path, aiohttp_client):
    config = make_config(
        mqtt_username="testuser",
        mqtt_password="supersecretpassword",
    )
    db_path = str(tmp_path / "test.db")
    from src.db import init_db
    await init_db(db_path)

    classifier = MagicMock()
    classifier.is_loaded = True
    mqtt_client = MagicMock()
    mqtt_client._running = True
    mqtt_client.ring_buffer = []

    app = create_app(
        config=config,
        db_path=db_path,
        classifier=classifier,
        mqtt_client=mqtt_client,
        static_path="/nonexistent",
    )

    with patch("src.api.aiohttp.ClientSession"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        text = await resp.text()

    assert "supersecretpassword" not in text
    data = json.loads(text)
    # Authenticated flag set correctly
    assert data["mqtt"]["authenticated"] is True


@pytest.mark.asyncio
async def test_status_anonymous_mqtt(tmp_path, aiohttp_client):
    app, db_path = make_app(tmp_path)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert data["mqtt"]["authenticated"] is False


@pytest.mark.asyncio
async def test_status_response_shape(tmp_path, aiohttp_client):
    """All required fields present for frontend StatusChip logic."""
    app, db_path = make_app(tmp_path)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert "mqtt" in data
    assert "connected" in data["mqtt"]
    assert "authenticated" in data["mqtt"]
    assert "frigate" in data
    assert "reachable" in data["frigate"]
    assert "model" in data
    assert "loaded" in data["model"]
    assert "database" in data
    assert "ok" in data["database"]
    assert "detections" in data["database"]
    assert "uptime_seconds" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_security_headers_present(tmp_path, aiohttp_client):
    app, db_path = make_app(tmp_path)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")

    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    # Must be SAMEORIGIN not DENY — HA Ingress uses iframe
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'self'" in csp
    assert "frame-ancestors 'none'" not in csp
