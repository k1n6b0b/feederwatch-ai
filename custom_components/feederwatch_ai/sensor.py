"""Sensors for FeederWatch AI."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FeederWatchCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FeederWatchCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            TotalDetectionsSensor(coordinator, entry),
            UniqueSpeciesSensor(coordinator, entry),
            PeakHourSensor(coordinator, entry),
            LastSpeciesSensor(coordinator, entry),
            MqttStatusSensor(coordinator, entry),
        ]
    )


class _FeederWatchSensor(CoordinatorEntity[FeederWatchCoordinator], SensorEntity):
    """Base class for FeederWatch sensors."""

    _attr_has_entity_name = True

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
            "sw_version": self.coordinator.data.status.get("version") if self.coordinator.data else None,
        }


class TotalDetectionsSensor(_FeederWatchSensor):
    _attr_name = "Total Detections"
    _attr_icon = "mdi:bird"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "detections"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_detections"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.status.get("database", {}).get("detections")


class UniqueSpeciesSensor(_FeederWatchSensor):
    _attr_name = "Unique Species"
    _attr_icon = "mdi:feather"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "species"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unique_species"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        # Count distinct scientific names in recent detections
        names = {
            d["scientific_name"]
            for d in self.coordinator.data.recent_detections
            if d.get("scientific_name")
        }
        return len(names)


class PeakHourSensor(_FeederWatchSensor):
    _attr_name = "Peak Hour Today"
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "h"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_peak_hour"

    @property
    def native_value(self):
        if not self.coordinator.data or not self.coordinator.data.recent_detections:
            return None
        from collections import Counter
        hours = [
            int(d["detected_at"][11:13])
            for d in self.coordinator.data.recent_detections
            if d.get("detected_at")
        ]
        if not hours:
            return None
        return Counter(hours).most_common(1)[0][0]


class LastSpeciesSensor(_FeederWatchSensor):
    _attr_name = "Last Species"
    _attr_icon = "mdi:bird"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_species"

    @property
    def native_value(self):
        if not self.coordinator.data or not self.coordinator.data.last_detection:
            return None
        return self.coordinator.data.last_detection.get("common_name")

    @property
    def extra_state_attributes(self):
        det = self.coordinator.data.last_detection if self.coordinator.data else None
        if not det:
            return {}
        return {
            "scientific_name": det.get("scientific_name"),
            "score": det.get("score"),
            "camera": det.get("camera_name"),
            "detected_at": det.get("detected_at"),
            "category": det.get("category_name"),
            "is_first_ever": det.get("is_first_ever", False),
        }


class MqttStatusSensor(_FeederWatchSensor):
    _attr_name = "MQTT Status"
    _attr_icon = "mdi:connection"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mqtt_status"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return "unknown"
        return "connected" if self.coordinator.data.status.get("mqtt", {}).get("connected") else "disconnected"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        mqtt = self.coordinator.data.status.get("mqtt", {})
        return {
            "host": mqtt.get("host"),
            "port": mqtt.get("port"),
            "authenticated": mqtt.get("authenticated"),
        }
