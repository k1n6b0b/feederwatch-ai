"""Image entity — last bird snapshot from FeederWatch AI."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDON_URL, DATA_COORDINATOR, DOMAIN
from .coordinator import FeederWatchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FeederWatchCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([LastBirdImage(hass, coordinator, entry)])


class LastBirdImage(CoordinatorEntity[FeederWatchCoordinator], ImageEntity):
    """Shows the snapshot of the most recently detected bird."""

    _attr_has_entity_name = True
    _attr_name = "Last Bird Snapshot"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: FeederWatchCoordinator,
        entry: ConfigEntry,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_last_snapshot"
        self._base_url = entry.data[CONF_ADDON_URL].rstrip("/")
        self._last_detection_id: int | None = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "FeederWatch AI",
            "manufacturer": "FeederWatch AI",
            "model": "Bird Classifier Add-on",
        }

    @property
    def image_url(self) -> str | None:
        if not self.coordinator.data or not self.coordinator.data.last_detection:
            return None
        det_id = self.coordinator.data.last_detection.get("id")
        if det_id is None:
            return None
        return f"{self._base_url}/api/v1/detections/{det_id}/snapshot"

    @property
    def image_last_updated(self) -> datetime | None:
        if not self.coordinator.data or not self.coordinator.data.last_detection:
            return None
        try:
            ts = self.coordinator.data.last_detection.get("detected_at", "")
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            # Add-on stores local naive time — attach local tz so HA is satisfied
            if dt.tzinfo is None:
                dt = dt.astimezone()
            return dt
        except (ValueError, AttributeError):
            return None

    async def async_image(self) -> bytes | None:
        url = self.image_url
        if not url:
            return None
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.debug("Snapshot returned %s for %s", resp.status, url)
                return None
        except Exception as exc:
            _LOGGER.warning("Failed to fetch snapshot: %s", exc)
            return None

    @property
    def extra_state_attributes(self):
        det = self.coordinator.data.last_detection if self.coordinator.data else None
        if not det:
            return {}
        return {
            "common_name": det.get("common_name"),
            "scientific_name": det.get("scientific_name"),
            "camera": det.get("camera_name"),
            "score": det.get("score"),
            "detected_at": det.get("detected_at"),
        }
