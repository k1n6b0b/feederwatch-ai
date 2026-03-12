"""
Tests for supervisor.py — HA Supervisor API auto-discovery.

All tests mock aiohttp to avoid real network calls.
SUPERVISOR_TOKEN env var is patched per-test.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.supervisor import discover_frigate_url, discover_mqtt


# ---------------------------------------------------------------------------
# discover_mqtt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discover_mqtt_no_token_returns_none():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("SUPERVISOR_TOKEN", None)
        result = await discover_mqtt()
    assert result is None


@pytest.mark.asyncio
async def test_discover_mqtt_returns_broker_info():
    payload = {
        "data": {
            "host": "core-mosquitto",
            "port": 1883,
            "username": "ha_user",
            "password": "secret",
            "ssl": False,
        }
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=payload)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_resp

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_mqtt()

    assert result is not None
    assert result["host"] == "core-mosquitto"
    assert result["port"] == 1883
    assert result["ssl"] is False
    # Password must not be forwarded
    assert "password" not in result


@pytest.mark.asyncio
async def test_discover_mqtt_non_200_returns_none():
    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_resp

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_mqtt()

    assert result is None


@pytest.mark.asyncio
async def test_discover_mqtt_network_error_returns_none():
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = Exception("connection refused")

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_mqtt()

    assert result is None


# ---------------------------------------------------------------------------
# discover_frigate_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discover_frigate_url_no_token_returns_none():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("SUPERVISOR_TOKEN", None)
        result = await discover_frigate_url()
    assert result is None


@pytest.mark.asyncio
async def test_discover_frigate_url_found_and_started():
    payload = {
        "data": {
            "addons": [
                {"slug": "core-mosquitto", "name": "Mosquitto broker", "state": "started"},
                {"slug": "ccab4aaf-frigate", "name": "Frigate NVR", "state": "started"},
            ]
        }
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=payload)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_resp

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_frigate_url()

    assert result == "http://ccab4aaf-frigate:5000"


@pytest.mark.asyncio
async def test_discover_frigate_url_not_in_addon_list():
    payload = {
        "data": {
            "addons": [
                {"slug": "core-mosquitto", "name": "Mosquitto broker", "state": "started"},
            ]
        }
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=payload)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_resp

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_frigate_url()

    assert result is None


@pytest.mark.asyncio
async def test_discover_frigate_url_found_but_stopped():
    payload = {
        "data": {
            "addons": [
                {"slug": "ccab4aaf-frigate", "name": "Frigate NVR", "state": "stopped"},
            ]
        }
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=payload)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_resp

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_frigate_url()

    assert result is None


@pytest.mark.asyncio
async def test_discover_frigate_url_network_error_returns_none():
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = Exception("timeout")

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}), \
         patch("src.supervisor.aiohttp.ClientSession", return_value=mock_session):
        result = await discover_frigate_url()

    assert result is None
