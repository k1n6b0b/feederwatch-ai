"""Notification logic for FeederWatch AI.

Three tiers:
  1. HA persistent notification — always, for first-ever species only
  2. HA event bus — every detection (feederwatch_ai_detection)
  3. Push via notify.<service> — configurable, all or new-species-only
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.persistent_notification import async_create as pn_create
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .coordinator import FeederWatchCoordinator

_LOGGER = logging.getLogger(__name__)

# Track which IDs we've already notified to avoid re-notifying on coordinator restart
_NOTIFIED_IDS: set[int] = set()


async def async_setup_notifications(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: FeederWatchCoordinator,
) -> None:
    """Register coordinator listener that fires notifications."""

    @callback
    def _on_update() -> None:
        if not coordinator.data or not coordinator.data.recent_detections:
            return

        det = coordinator.data.recent_detections[0]
        det_id = det.get("id")
        if det_id is None or det_id in _NOTIFIED_IDS:
            return
        _NOTIFIED_IDS.add(det_id)

        # Limit set size to avoid unbounded growth
        if len(_NOTIFIED_IDS) > 2000:
            oldest = sorted(_NOTIFIED_IDS)[:500]
            for oid in oldest:
                _NOTIFIED_IDS.discard(oid)

        is_first_ever = det.get("is_first_ever", False)
        common = det.get("common_name", "Unknown bird")
        scientific = det.get("scientific_name", "")
        camera = det.get("camera_name", "")
        score = det.get("score")
        score_str = f"{round(score * 100)}% confidence" if score else "Frigate classified"

        # --- Tier 1: Persistent notification for first-ever species ---
        if is_first_ever:
            pn_create(
                hass,
                message=(
                    f"**{common}** (*{scientific}*) was spotted for the first time!\n"
                    f"Camera: {camera} · {score_str}"
                ),
                title="🐦 New species at your feeder!",
                notification_id=f"feederwatch_ai_new_species_{det_id}",
            )
            _LOGGER.info("New species first ever: %s", common)

        # --- Tier 3: Push notification via notify service ---
        notify_service: str = entry.options.get("notify_service", "").strip()
        new_species_only: bool = entry.options.get("notify_new_species_only", False)

        if notify_service and (not new_species_only or is_first_ever):
            _send_push(hass, notify_service, common, scientific, camera, score_str, is_first_ever)

    entry.async_on_unload(coordinator.async_add_listener(_on_update))


def _send_push(
    hass: HomeAssistant,
    service: str,
    common: str,
    scientific: str,
    camera: str,
    score_str: str,
    is_first_ever: bool,
) -> None:
    """Call notify.<service> with detection details."""
    parts = service.split(".", 1)
    if len(parts) != 2:
        _LOGGER.warning("Invalid notify_service %r — expected 'notify.service_name'", service)
        return

    domain, svc = parts
    title = f"{'🆕 New species: ' if is_first_ever else '🐦 '}{common}"
    message = f"{scientific} · {camera} · {score_str}"

    hass.async_create_task(
        hass.services.async_call(
            domain,
            svc,
            service_data={"title": title, "message": message},
            blocking=False,
        )
    )
