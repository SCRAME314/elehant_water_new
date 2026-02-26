"""Sensor platform for Elehant Water."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolume
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    UNIT_CUBIC_METERS,
    UNIT_LITERS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor platform."""
    device_id = entry.data[CONF_DEVICE_ID]
    device_name = entry.data[CONF_DEVICE_NAME]
    coordinator = hass.data[DOMAIN][device_id]

    # Create sensors
    entities = [
        ElehantCounterSensor(coordinator, entry, device_id, device_name),
        ElehantBatterySensor(coordinator, entry, device_id, device_name),
        ElehantTemperatureSensor(coordinator, entry, device_id, device_name),
    ]
    async_add_entities(entities)


class ElehantBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Elehant sensors."""

    def __init__(self, coordinator, entry, device_id, device_name, sensor_type):
        """Initialize."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{device_id}_{sensor_type}"
        self._attr_name = f"{device_name} {sensor_type.capitalize()}"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Elehant",
            "model": "Water Meter",
        }


class ElehantCounterSensor(ElehantBaseSensor):
    """Representation of a counter sensor."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize counter sensor."""
        super().__init__(coordinator, entry, device_id, device_name, "counter")
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "counter_liters" in self.coordinator.data:
            liters = self.coordinator.data["counter_liters"]
            unit = self.coordinator.data.get("unit", UNIT_CUBIC_METERS)
            if unit == UNIT_CUBIC_METERS:
                return liters / 1000.0  # Convert liters to m³
            return liters
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.coordinator.data:
            unit = self.coordinator.data.get("unit", UNIT_CUBIC_METERS)
            if unit == UNIT_CUBIC_METERS:
                return UnitOfVolume.CUBIC_METERS
            return UnitOfVolume.LITERS
        return UnitOfVolume.CUBIC_METERS  # Default


class ElehantBatterySensor(ElehantBaseSensor):
    """Representation of a battery sensor."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize battery sensor."""
        super().__init__(coordinator, entry, device_id, device_name, "battery")
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("battery")
        return None


class ElehantTemperatureSensor(ElehantBaseSensor):
    """Representation of a temperature sensor."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize temperature sensor."""
        super().__init__(coordinator, entry, device_id, device_name, "temperature")
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("temperature")
        return None
