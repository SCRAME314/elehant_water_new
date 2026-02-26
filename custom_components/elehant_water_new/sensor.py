"""Sensor platform for Elehant Water."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfVolume,
    UnitOfTemperature,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_COUNTERS,
    CONF_COUNTER_ID,
    CONF_COUNTER_TYPE,
    CONF_NAME,
    COUNTER_TYPE_GAS,
    COUNTER_TYPE_WATER,
    DATA_COORDINATOR,
    DATA_DEVICES,
    DOMAIN,
    ATTR_BATTERY_LEVEL,
    ATTR_RSSI,
    ATTR_LAST_SEEN,
    ATTR_TEMPERATURE,
    ATTR_TARIFF_1,
    ATTR_TARIFF_2,
    ATTR_CURRENT_TARIFF,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elehant sensor entries."""
    entry_id = config_entry.entry_id
    data = hass.data[DOMAIN][entry_id]
    coordinator = data[DATA_COORDINATOR]
    config = data[DATA_CONFIG]
    
    entities = []
    
    # Создаем сенсоры для каждого настроенного счетчика
    for counter_config in config.get(CONF_COUNTERS, []):
        counter_id = counter_config[CONF_COUNTER_ID]
        counter_type = counter_config[CONF_COUNTER_TYPE]
        name = counter_config.get(CONF_NAME, f"Elehant {counter_id}")
        
        entities.append(
            ElehantCounterSensor(
                coordinator,
                entry_id,
                counter_id,
                counter_type,
                name,
            )
        )
    
    if entities:
        async_add_entities(entities)


class ElehantCounterSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Elehant counter sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        counter_id: str,
        counter_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self.entry_id = entry_id
        self.counter_id = counter_id
        self.counter_type = counter_type
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{counter_id}"
        
        # Настройка единиц измерения и класса
        if counter_type == COUNTER_TYPE_GAS:
            self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
            self._attr_device_class = SensorDeviceClass.GAS
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:  # water
            self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        
        self._attr_extra_state_attributes = {}
        self._available = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.counter_id)},
            name=self._attr_name,
            manufacturer="Elehant",
            model=f"Counter ({self.counter_type})",
            sw_version="1.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            # Ищем наше устройство среди найденных
            for mac, device_data in self.coordinator.data.items():
                if device_data.get("counter_id") == self.counter_id:
                    self._available = True
                    
                    # Обновляем атрибуты
                    self._attr_extra_state_attributes = {
                        ATTR_RSSI: device_data.get("rssi"),
                        ATTR_LAST_SEEN: device_data.get("last_seen").isoformat() 
                            if device_data.get("last_seen") else None,
                    }
                    
                    # Добавляем специфичные атрибуты в зависимости от типа
                    if ATTR_TEMPERATURE in device_data:
                        self._attr_extra_state_attributes[ATTR_TEMPERATURE] = device_data[ATTR_TEMPERATURE]
                    
                    if ATTR_TARIFF_1 in device_data:
                        self._attr_extra_state_attributes[ATTR_TARIFF_1] = device_data[ATTR_TARIFF_1]
                        self._attr_extra_state_attributes[ATTR_TARIFF_2] = device_data[ATTR_TARIFF_2]
                        self._attr_extra_state_attributes[ATTR_CURRENT_TARIFF] = device_data[ATTR_CURRENT_TARIFF]
                    
                    return device_data.get("state")
            
            self._available = False
            return None
        
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
