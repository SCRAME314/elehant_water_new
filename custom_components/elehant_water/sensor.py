"""Platform for Elehant Water sensor integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_TYPE,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_MEASUREMENT_WATER,
    CONF_MEASUREMENT_GAS,
    CONF_SCAN_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_WATER_TYPE,
    CONF_NAME_TEMP,
    DEVICE_TYPE_WATER,
    DEVICE_TYPE_GAS,
    WATER_TYPE_HOT,
    WATER_TYPE_COLD,
    MEASUREMENT_LITERS,
    MEASUREMENT_CUBIC_METERS,
    ATTR_BATTERY_LEVEL,
    ATTR_RSSI,
    ATTR_TEMPERATURE,
    ATTR_LAST_SEEN,
    ATTR_COUNTER_VALUE,
)

_LOGGER = logging.getLogger(__name__)

# Elehant BLE Service UUID
ELEHANT_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
ELEHANT_MANUFACTURER_ID = 0xFFFF  # Elehant manufacturer ID

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elehant Water sensors based on a config entry."""
    _LOGGER.debug("Setting up Elehant Water sensors from config entry")

    config = entry.data
    devices = config.get(CONF_DEVICES, [])
    measurement_water = config.get(CONF_MEASUREMENT_WATER, MEASUREMENT_CUBIC_METERS)
    measurement_gas = config.get(CONF_MEASUREMENT_GAS, MEASUREMENT_CUBIC_METERS)
    scan_duration = config.get(CONF_SCAN_DURATION, 10)
    scan_interval = config.get(CONF_SCAN_INTERVAL, 600)

    entities = []
    elehant_devices = {}

    # Create entities for each configured device
    for device_config in devices:
        device_id = str(device_config[CONF_ID])
        device_type = device_config[CONF_TYPE]
        name = device_config[CONF_NAME]
        water_type = device_config.get(CONF_WATER_TYPE)
        name_temp = device_config.get(CONF_NAME_TEMP)

        _LOGGER.debug(f"Creating sensor for device {device_id} - {name}")

        # Determine measurement unit
        if device_type == DEVICE_TYPE_WATER:
            unit = measurement_water
        else:
            unit = measurement_gas

        # Create main counter sensor
        sensor = ElehantCounterSensor(
            device_id,
            name,
            device_type,
            unit,
            water_type,
        )
        entities.append(sensor)
        elehant_devices[device_id] = sensor

        # Create temperature sensor if name_temp is provided
        if name_temp:
            temp_sensor = ElehantTemperatureSensor(
                device_id,
                name_temp,
                device_type,
            )
            entities.append(temp_sensor)
            elehant_devices[f"{device_id}_temp"] = temp_sensor

    if not entities:
        _LOGGER.warning("No Elehant devices configured")
        return

    # Add all entities
    async_add_entities(entities)

    # Start the scanner
    scanner = ElehantScanner(
        hass,
        elehant_devices,
        scan_duration,
        scan_interval,
    )
    await scanner.async_start()


class ElehantCounterSensor(SensorEntity):
    """Representation of an Elehant counter sensor."""

    def __init__(
        self,
        device_id: str,
        name: str,
        device_type: str,
        unit: str,
        water_type: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._device_id = device_id
        self._device_type = device_type
        self._water_type = water_type
        self._unit = unit
        self._attr_name = name
        self._attr_unique_id = f"elehant_{device_id}_counter"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.WATER if device_type == DEVICE_TYPE_WATER else SensorDeviceClass.GAS
        self._attr_native_unit_of_measurement = (
            UnitOfVolume.CUBIC_METERS if unit == MEASUREMENT_CUBIC_METERS else UnitOfVolume.LITERS
        )
        self._attr_icon = "mdi:water" if device_type == DEVICE_TYPE_WATER else "mdi:fire"
        self._attr_extra_state_attributes = {}
        self._attr_native_value = None
        self._last_seen = None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="Elehant",
            model=f"{self._device_type.capitalize()} Meter",
            sw_version="1.0",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._attr_native_value

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        """Handle updated data from scanner."""
        if "counter" in data:
            # Convert counter value based on unit
            counter_value = float(data["counter"])
            if self._unit == MEASUREMENT_CUBIC_METERS and self._device_type == DEVICE_TYPE_WATER:
                # Convert from liters to cubic meters (1 m³ = 1000 L)
                counter_value = counter_value / 1000
            self._attr_native_value = counter_value

        # Update attributes
        if "battery" in data:
            self._attr_extra_state_attributes[ATTR_BATTERY_LEVEL] = data["battery"]
        if "rssi" in data:
            self._attr_extra_state_attributes[ATTR_RSSI] = data["rssi"]
        
        self._last_seen = data.get("timestamp")
        if self._last_seen:
            self._attr_extra_state_attributes[ATTR_LAST_SEEN] = self._last_seen

        self.async_write_ha_state()


class ElehantTemperatureSensor(SensorEntity):
    """Representation of an Elehant temperature sensor."""

    def __init__(
        self,
        device_id: str,
        name: str,
        device_type: str,
    ) -> None:
        """Initialize the sensor."""
        self._device_id = device_id
        self._device_type = device_type
        self._attr_name = name
        self._attr_unique_id = f"elehant_{device_id}_temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"
        self._attr_extra_state_attributes = {}
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        """Handle updated data from scanner."""
        if "temperature" in data:
            self._attr_native_value = float(data["temperature"])
            self.async_write_ha_state()


class ElehantScanner:
    """Scan for Elehant devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        devices: dict[str, ElehantCounterSensor | ElehantTemperatureSensor],
        scan_duration: int,
        scan_interval: int,
    ) -> None:
        """Initialize scanner."""
        self.hass = hass
        self.devices = devices
        self.scan_duration = scan_duration
        self.scan_interval = scan_interval
        self._scanning = False
        self._cancel_interval = None

    async def async_start(self) -> None:
        """Start scanning."""
        _LOGGER.debug("Starting Elehant scanner")
        self._cancel_interval = async_track_time_interval(
            self.hass,
            self.async_scan,
            timedelta(seconds=self.scan_interval),
        )
        # Start first scan immediately
        await self.async_scan()

    async def async_stop(self) -> None:
        """Stop scanning."""
        if self._cancel_interval:
            self._cancel_interval()
            self._cancel_interval = None

    async def async_scan(self, now=None) -> None:
        """Perform a scan."""
        if self._scanning:
            _LOGGER.debug("Scan already in progress")
            return

        self._scanning = True
        _LOGGER.debug(f"Starting Elehant scan for {self.scan_duration} seconds")

        try:
            # Get all discovered devices
            service_infos = async_discovered_service_info(self.hass)
            
            for service_info in service_infos:
                await self._process_device(service_info)

            # Start advertisement processing for new devices
            await self._process_advertisements()

        except Exception as err:
            _LOGGER.error(f"Error during scan: {err}")
        finally:
            self._scanning = False

    async def _process_advertisements(self) -> None:
        """Process BLE advertisements."""
        def device_detected(service_info: BluetoothServiceInfoBleak) -> bool:
            """Process detected device."""
            return self._process_device_sync(service_info)

        try:
            await async_process_advertisements(
                self.hass,
                device_detected,
                {"match": {}},
                BluetoothScanningMode.ACTIVE,
                self.scan_duration,
            )
        except asyncio.TimeoutError:
            _LOGGER.debug("Advertisement processing timeout")
        except Exception as err:
            _LOGGER.error(f"Error processing advertisements: {err}")

    def _process_device_sync(self, service_info: BluetoothServiceInfoBleak) -> bool:
        """Synchronously process a device."""
        if not self._is_elehant_device(service_info):
            return False

        # Extract device data
        device_id = self._extract_device_id(service_info)
        if not device_id or device_id not in self.devices:
            return False

        # Parse the advertisement data
        data = self._parse_advertisement_data(service_info)
        if data:
            # Update all sensors for this device
            main_sensor = self.devices.get(device_id)
            if main_sensor and isinstance(main_sensor, ElehantCounterSensor):
                main_sensor._handle_update(data)

            temp_sensor = self.devices.get(f"{device_id}_temp")
            if temp_sensor and isinstance(temp_sensor, ElehantTemperatureSensor):
                temp_sensor._handle_update(data)

        return True

    async def _process_device(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Process a discovered device."""
        self._process_device_sync(service_info)

    def _is_elehant_device(self, service_info: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is an Elehant sensor."""
        # Check service UUID
        if ELEHANT_SERVICE_UUID in service_info.service_uuids:
            return True

        # Check manufacturer data
        if service_info.manufacturer_data and ELEHANT_MANUFACTURER_ID in service_info.manufacturer_data:
            return True

        # Check device name
        if service_info.name and "ELEHANT" in service_info.name.upper():
            return True

        return False

    def _extract_device_id(self, service_info: BluetoothServiceInfoBleak) -> str | None:
        """Extract device ID from advertisement data."""
        # Try to extract from manufacturer data
        if service_info.manufacturer_data and ELEHANT_MANUFACTURER_ID in service_info.manufacturer_data:
            mfg_data = service_info.manufacturer_data[ELEHANT_MANUFACTURER_ID]
            if len(mfg_data) >= 4:
                # Device ID is usually in the first 4 bytes
                device_id = int.from_bytes(mfg_data[0:4], byteorder="little")
                return str(device_id)

        # Try to extract from service data
        for uuid, data in service_info.service_data.items():
            if ELEHANT_SERVICE_UUID in uuid:
                if len(data) >= 4:
                    device_id = int.from_bytes(data[0:4], byteorder="little")
                    return str(device_id)

        # Fallback to MAC address
        if service_info.address:
            return service_info.address.replace(":", "")

        return None

    def _parse_advertisement_data(self, service_info: BluetoothServiceInfoBleak) -> dict[str, Any] | None:
        """Parse the advertisement data from Elehant device."""
        data = {
            "rssi": service_info.rssi,
            "timestamp": service_info.time,
        }

        # Try to parse manufacturer data
        if service_info.manufacturer_data and ELEHANT_MANUFACTURER_ID in service_info.manufacturer_data:
            mfg_data = service_info.manufacturer_data[ELEHANT_MANUFACTURER_ID]
            if len(mfg_data) >= 8:
                # Counter value is usually in bytes 4-8
                data["counter"] = int.from_bytes(mfg_data[4:8], byteorder="little")
                # Battery level might be in byte 8 or 9
                if len(mfg_data) >= 9:
                    data["battery"] = mfg_data[8]
                # Temperature might be in bytes 10-11
                if len(mfg_data) >= 12:
                    temp_raw = int.from_bytes(mfg_data[10:12], byteorder="little", signed=True)
                    data["temperature"] = temp_raw / 10.0

        # Try to parse service data
        for uuid, srv_data in service_info.service_data.items():
            if ELEHANT_SERVICE_UUID in uuid and len(srv_data) >= 8:
                data["counter"] = int.from_bytes(srv_data[4:8], byteorder="little")
                if len(srv_data) >= 9:
                    data["battery"] = srv_data[8]
                if len(srv_data) >= 12:
                    temp_raw = int.from_bytes(srv_data[10:12], byteorder="little", signed=True)
                    data["temperature"] = temp_raw / 10.0
                break

        return data if "counter" in data else None
