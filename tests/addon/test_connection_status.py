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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.api import create_app
from src.config import Config


def make_config(**overrides) -> Config:
    defaults = dict(
        frigate_api_url="http://frigate:5000",
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
    mqtt_client._connected = mqtt_running
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
    mqtt_client._connected = True
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
async def test_status_discovery_field_present(tmp_path, aiohttp_client):
    """Fix 5: /api/v1/status always includes a 'discovery' key."""
    app, db_path = make_app(tmp_path)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"), \
         patch("src.api.discover_mqtt", new_callable=AsyncMock, return_value=None), \
         patch("src.api.discover_frigate_url", new_callable=AsyncMock, return_value=None):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert "discovery" in data
    assert "mqtt" in data["discovery"]
    assert "frigate_url" in data["discovery"]


@pytest.mark.asyncio
async def test_status_discovery_contains_supervisor_mqtt(tmp_path, aiohttp_client):
    """Fix 5: discovery.mqtt is populated when Supervisor returns broker info."""
    app, db_path = make_app(tmp_path)
    from src.db import init_db
    await init_db(db_path)

    mqtt_info = {"host": "core-mosquitto", "port": 1883, "username": "ha_user", "ssl": False}

    with patch("src.api.aiohttp.ClientSession"), \
         patch("src.api.discover_mqtt", new_callable=AsyncMock, return_value=mqtt_info), \
         patch("src.api.discover_frigate_url", new_callable=AsyncMock, return_value=None):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert data["discovery"]["mqtt"]["host"] == "core-mosquitto"
    assert data["discovery"]["mqtt"]["port"] == 1883


@pytest.mark.asyncio
async def test_status_discovery_contains_frigate_url(tmp_path, aiohttp_client):
    """Fix 5: discovery.frigate_url is populated when Supervisor returns Frigate add-on."""
    app, db_path = make_app(tmp_path)
    from src.db import init_db
    await init_db(db_path)

    with patch("src.api.aiohttp.ClientSession"), \
         patch("src.api.discover_mqtt", new_callable=AsyncMock, return_value=None), \
         patch("src.api.discover_frigate_url", new_callable=AsyncMock, return_value="http://ccab4aaf-frigate:5000"):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert data["discovery"]["frigate_url"] == "http://ccab4aaf-frigate:5000"


@pytest.mark.asyncio
async def test_status_mqtt_error_type_auth(tmp_path, aiohttp_client):
    """error_type: 'auth' is returned when mqtt_client._error_type == 'auth'."""
    db_path = str(tmp_path / "test.db")
    from src.db import init_db
    await init_db(db_path)

    classifier = MagicMock()
    classifier.is_loaded = True
    mqtt_client = MagicMock()
    mqtt_client._connected = False
    mqtt_client._error_type = "auth"
    mqtt_client.last_error = "Connection refused: Bad username or password"
    mqtt_client.error_type = "auth"
    mqtt_client.ring_buffer = []

    config = make_config()
    app = create_app(
        config=config,
        db_path=db_path,
        classifier=classifier,
        mqtt_client=mqtt_client,
        static_path="/nonexistent",
    )

    with patch("src.api.aiohttp.ClientSession"), \
         patch("src.api.discover_mqtt", new_callable=AsyncMock, return_value=None), \
         patch("src.api.discover_frigate_url", new_callable=AsyncMock, return_value=None):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert data["mqtt"]["error_type"] == "auth"
    assert data["mqtt"]["connected"] is False


@pytest.mark.asyncio
async def test_status_mqtt_error_type_none_when_no_client(tmp_path, aiohttp_client):
    """error_type is null when mqtt_client is None (model not loaded)."""
    db_path = str(tmp_path / "test.db")
    from src.db import init_db
    await init_db(db_path)

    classifier = MagicMock()
    classifier.is_loaded = False

    config = make_config()
    app = create_app(
        config=config,
        db_path=db_path,
        classifier=classifier,
        static_path="/nonexistent",
    )
    # No mqtt_client set in app

    with patch("src.api.aiohttp.ClientSession"), \
         patch("src.api.discover_mqtt", new_callable=AsyncMock, return_value=None), \
         patch("src.api.discover_frigate_url", new_callable=AsyncMock, return_value=None):
        client = await aiohttp_client(app)
        resp = await client.get("/api/v1/status")
        data = await resp.json()

    assert data["mqtt"]["error_type"] is None


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
