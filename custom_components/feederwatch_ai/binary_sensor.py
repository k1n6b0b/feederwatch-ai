"""Binary sensors for FeederWatch AI.

Entities created:
  - binary_sensor.feederwatch_ai_classified_bird_present  (aggregate)
  - binary_sensor.feederwatch_ai_<slug>_present           (per species, dynamic)

Per-species sensors are created/updated dynamically as new species appear.
They are never removed automatically — species seen once get a permanent sensor.
"""

from __future__ import annotations

import logging
import re

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FeederWatchCoordinator

_LOGGER = logging.getLogger(__name__)


def _species_slug(scientific_name: str) -> str:
    """Convert scientific name to a safe entity ID component.

    Example: "Turdus migratorius" → "turdus_migratorius"
    """
    return re.sub(r"[^a-z0-9]+", "_", scientific_name.lower()).strip("_")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FeederWatchCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Aggregate sensor always present
    aggregate = ClassifiedBirdPresentSensor(coordinator, entry)
    async_add_entities([aggregate])

    # Track which per-species sensors have been added so we don't duplicate
    known_species: set[str] = set()

    @callback
    def _add_new_species() -> None:
        if not coordinator.data:
            return
        new_sensors: list[SpeciesPresentSensor] = []
        for det in coordinator.data.recent_detections:
            name = det.get("scientific_name")
            common = det.get("common_name", name)
            if name and name not in known_species:
                known_species.add(name)
                new_sensors.append(SpeciesPresentSensor(coordinator, entry, name, common))
        if new_sensors:
            _LOGGER.debug("Adding %d new species binary sensors", len(new_sensors))
            async_add_entities(new_sensors)

    # Add species already known from the first coordinator refresh
    _add_new_species()

    # Add new species as they appear in future updates
    entry.async_on_unload(coordinator.async_add_listener(_add_new_species))


class _FeederWatchBinarySensor(CoordinatorEntity[FeederWatchCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: FeederWatchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "FeederWatch AI",
            "manufacturer": "FeederWatch AI",
            "model": "Bird Classifier Add-on",
        }


class ClassifiedBirdPresentSensor(_FeederWatchBinarySensor):
    """True when any classified bird was detected in the last 5 minutes."""

    _attr_name = "Classified Bird Present"
    _attr_icon = "mdi:bird"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_classified_bird_present"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        return len(self.coordinator.data.present_species) > 0

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "present_species": sorted(self.coordinator.data.present_species),
            "count": len(self.coordinator.data.present_species),
        }


class SpeciesPresentSensor(_FeederWatchBinarySensor):
    """True when a specific species was detected in the last 5 minutes."""

    def __init__(
        self,
        coordinator: FeederWatchCoordinator,
        entry: ConfigEntry,
        scientific_name: str,
        common_name: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._scientific_name = scientific_name
        self._common_name = common_name
        slug = _species_slug(scientific_name)
        self._attr_unique_id = f"{entry.entry_id}_species_{slug}_present"
        self._attr_name = f"{common_name} Present"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        return self._scientific_name in self.coordinator.data.present_species

    @property
    def extra_state_attributes(self):
        return {
            "scientific_name": self._scientific_name,
            "common_name": self._common_name,
        }
