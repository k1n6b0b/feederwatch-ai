"""
HA Supervisor API helpers for auto-discovery of MQTT and Frigate.

All functions return None when:
  - SUPERVISOR_TOKEN is not set (dev / non-HA environment)
  - The Supervisor request fails for any reason

Results are safe to ignore — discovery is advisory only.
"""

from __future__ import annotations

import logging
import os

import aiohttp

_LOGGER = logging.getLogger(__name__)

_SUPERVISOR_BASE = "http://supervisor"
_TIMEOUT = aiohttp.ClientTimeout(total=3)
_FRIGATE_SLUG = "ccab4aaf-frigate"


def _token() -> str | None:
    return os.environ.get("SUPERVISOR_TOKEN")


async def discover_mqtt() -> dict | None:
    """Query Supervisor for the MQTT service broker details.

    Returns a dict with keys: host, port, username, password, ssl
    or None if unavailable.
    """
    token = _token()
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_SUPERVISOR_BASE}/services/mqtt",
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
                data = payload.get("data", payload)
                return {
                    "host": data.get("host"),
                    "port": data.get("port"),
                    "username": data.get("username"),
                    "ssl": data.get("ssl", False),
                }
    except Exception as exc:
        _LOGGER.debug("Supervisor MQTT discovery failed: %s", exc)
        return None


async def discover_frigate_url() -> str | None:
    """Query Supervisor add-on list for the Frigate add-on and return its base URL.

    Returns a URL like "http://ccab4aaf-frigate:5000" or None if not found.
    """
    token = _token()
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_SUPERVISOR_BASE}/addons",
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
                addons = payload.get("data", {}).get("addons", [])
                for addon in addons:
                    if addon.get("slug") == _FRIGATE_SLUG and addon.get("state") == "started":
                        return f"http://{_FRIGATE_SLUG}:5000"
                return None
    except Exception as exc:
        _LOGGER.debug("Supervisor Frigate discovery failed: %s", exc)
        return None
