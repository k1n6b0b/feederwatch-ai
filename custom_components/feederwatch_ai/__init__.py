"""FeederWatch AI Home Assistant Integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN, EVENT_NEW_DETECTION
from .coordinator import FeederWatchCoordinator
from .notifications import async_setup_notifications

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.IMAGE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FeederWatch AI from a config entry."""
    coordinator = FeederWatchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Fire HA events + push notifications whenever the coordinator sees new detections
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _handle_coordinator_update(hass, entry, coordinator)
        )
    )

    # Set up notification listeners (options-based push notify target)
    await async_setup_notifications(hass, entry, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


def _handle_coordinator_update(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: FeederWatchCoordinator,
) -> None:
    """Fire HA events for each detection in the most recent update."""
    data = coordinator.data
    if not data or not data.recent_detections:
        return

    # Only fire for the most-recent detection to avoid event floods on restart
    det = data.recent_detections[0]
    hass.bus.async_fire(
        EVENT_NEW_DETECTION,
        {
            "common_name": det.get("common_name"),
            "scientific_name": det.get("scientific_name"),
            "camera": det.get("camera_name"),
            "score": det.get("score"),
            "category": det.get("category_name"),
            "is_first_ever": det.get("is_first_ever", False),
            "detected_at": det.get("detected_at"),
            "frigate_event_id": det.get("frigate_event_id"),
        },
    )


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
