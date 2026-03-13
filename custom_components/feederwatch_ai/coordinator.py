"""DataUpdateCoordinator for FeederWatch AI."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ADDON_URL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FeederWatchData:
    """Snapshot of all data fetched in one coordinator update."""

    # /api/v1/status
    status: dict[str, Any] = field(default_factory=dict)

    # /api/v1/detections/recent  (newest first, up to 20)
    recent_detections: list[dict[str, Any]] = field(default_factory=list)

    # Derived: set of scientific_names currently "present" (latest event is active)
    present_species: set[str] = field(default_factory=set)

    # Derived: last detection dict (for image entity)
    last_detection: dict[str, Any] | None = None


class FeederWatchCoordinator(DataUpdateCoordinator[FeederWatchData]):
    """Polls the FeederWatch AI add-on REST API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._base_url = entry.data[CONF_ADDON_URL].rstrip("/")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> FeederWatchData:
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with session.get(
                f"{self._base_url}/api/v1/status", timeout=timeout
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Status endpoint returned {resp.status}")
                status = await resp.json()

            async with session.get(
                f"{self._base_url}/api/v1/detections/recent?limit=20", timeout=timeout
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Detections endpoint returned {resp.status}")
                recent = await resp.json()

        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"Cannot reach FeederWatch AI add-on: {exc}") from exc

        # Determine which species are present: the most recent detection
        # per species tells us if they're currently active.  We consider
        # a species "present" if its most-recent detection was within the
        # last 5 minutes (mirrors the add-on's 5-minute safety timeout).
        from datetime import datetime

        # Add-on stores detected_at in local time (naive, no tz suffix) —
        # compare against datetime.now() (also local, naive) to avoid tz mismatch.
        now = datetime.now()
        present: set[str] = set()
        seen: set[str] = set()
        last: dict[str, Any] | None = recent[0] if recent else None

        for det in recent:
            name = det.get("scientific_name")
            if name and name not in seen:
                seen.add(name)
                try:
                    detected_at = datetime.fromisoformat(det["detected_at"])
                    if (now - detected_at).total_seconds() < 300:
                        present.add(name)
                except (KeyError, ValueError):
                    pass

        return FeederWatchData(
            status=status,
            recent_detections=recent,
            present_species=present,
            last_detection=last,
        )
