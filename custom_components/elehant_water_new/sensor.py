"""Platform for Elehant Water sensor integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any
import subprocess

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

    # Проверяем доступные Bluetooth адаптеры
    try:
        result = subprocess.run(['hciconfig'], capture_output=True, text=True, timeout=5)
        _LOGGER.info(f"🔵 Доступные Bluetooth адаптеры:\n{result.stdout}")
    except Exception as e:
        _LOGGER.error(f"Не удалось проверить Bluetooth адаптеры: {e}")

    config = entry.data
    devices = config.get(CONF_DEVICES, [])
    measurement_water = config.get(CONF_MEASUREMENT_WATER, MEASUREMENT_CUBIC_METERS)
    measurement_gas = config.get(CONF_MEASUREMENT_GAS, MEASUREMENT_CUBIC_METERS)
    scan_duration = config.get(CONF_SCAN_DURATION, 10)
    scan_interval = config.get(CONF_SCAN_INTERVAL, 600)

    _LOGGER.info(f"📊 Настройки сканирования: длительность={scan_duration}с, интервал={scan_interval}с")
    _LOGGER.info(f"📊 Найдено устройств в конфиге: {len(devices)}")

    entities = []
    elehant_devices = {}

    # Create entities for each configured device
    for i, device_config in enumerate(devices):
        device_id = str(device_config[CONF_ID])
        device_type = device_config[CONF_TYPE]
        name = device_config[CONF_NAME]
        water_type = device_config.get(CONF_WATER_TYPE)
        name_temp = device_config.get(CONF_NAME_TEMP)

        _LOGGER.debug(f"📝 Создание сенсора для устройства {i+1}: ID={device_id}, тип={device_type}, имя={name}")

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
            _LOGGER.debug(f"🌡️ Создание сенсора температуры для {device_id}: {name_temp}")
            temp_sensor = ElehantTemperatureSensor(
                device_id,
                name_temp,
                device_type,
            )
            entities.append(temp_sensor)
            elehant_devices[f"{device_id}_temp"] = temp_sensor

    if not entities:
        _LOGGER.warning("⚠️ Нет настроенных устройств Elehant")
        return

    # Add all entities
    async_add_entities(entities)
    _LOGGER.info(f"✅ Добавлено {len(entities)} сенсоров Elehant")

    # Start the scanner
    scanner = ElehantScanner(
        hass,
        elehant_devices,
        scan_duration,
        scan_interval,
    )
    
    # Запускаем сканер в фоне
    hass.loop.create_task(scanner.async_start())
    
    # Сохраняем сканер в hass.data для возможного доступа позже
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["scanner"] = scanner
    
    _LOGGER.info("🚀 Сканер Elehant запущен в фоновом режиме")
    return True


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
        
        _LOGGER.debug(f"🏭 Инициализирован счетчик {device_id} с именем {name}")

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
        old_value = self._attr_native_value
        
        if "counter" in data:
            # Convert counter value based on unit
            counter_value = float(data["counter"])
            if self._unit == MEASUREMENT_CUBIC_METERS and self._device_type == DEVICE_TYPE_WATER:
                # Convert from liters to cubic meters (1 m³ = 1000 L)
                counter_value = counter_value / 1000
            
            self._attr_native_value = counter_value
            _LOGGER.debug(f"📊 Счетчик {self._device_id}: {old_value} -> {counter_value} (сырые данные: {data['counter']})")

        # Update attributes
        if "battery" in data:
            self._attr_extra_state_attributes[ATTR_BATTERY_LEVEL] = data["battery"]
            _LOGGER.debug(f"🔋 Счетчик {self._device_id}: батарея {data['battery']}%")
        
        if "rssi" in data:
            self._attr_extra_state_attributes[ATTR_RSSI] = data["rssi"]
            _LOGGER.debug(f"📶 Счетчик {self._device_id}: RSSI {data['rssi']} dBm")
        
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
        
        _LOGGER.debug(f"🌡️ Инициализирован датчик температуры {device_id}")

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
            old_temp = self._attr_native_value
            self._attr_native_value = float(data["temperature"])
            _LOGGER.debug(f"🌡️ Температура {self._device_id}: {old_temp} -> {self._attr_native_value}°C")
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
        self._scan_count = 0
        
        _LOGGER.debug(f"🔍 Сканер инициализирован: длительность={scan_duration}с, интервал={scan_interval}с")

    async def async_start(self) -> None:
        """Start scanning."""
        _LOGGER.info("🔵 Запуск сканера Elehant")
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
            _LOGGER.info("🛑 Сканер Elehant остановлен")

    async def async_scan(self, now=None) -> None:
        """Perform a scan."""
        if self._scanning:
            _LOGGER.debug("⏳ Сканирование уже выполняется, пропускаем")
            return

        self._scanning = True
        self._scan_count += 1
        _LOGGER.info(f"🔍 [{self._scan_count}] Начало сканирования Elehant на {self.scan_duration} секунд")

        try:
            # Get all discovered devices
            service_infos = async_discovered_service_info(self.hass)
            _LOGGER.info(f"📡 Всего найдено BLE устройств: {len(service_infos)}")
            
            for i, service_info in enumerate(service_infos):
                _LOGGER.debug(f"  BLE устройство {i+1}: {service_info.address} | Имя: {service_info.name} | RSSI: {service_info.rssi} | UUIDs: {service_info.service_uuids}")
                await self._process_device(service_info)

            # Start advertisement processing for new devices
            _LOGGER.debug("🎯 Запуск обработки рекламных пакетов...")
            await self._process_advertisements()

        except Exception as err:
            _LOGGER.error(f"❌ Ошибка во время сканирования: {err}", exc_info=True)
        finally:
            self._scanning = False
            _LOGGER.info(f"✅ [{self._scan_count}] Сканирование завершено")

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
            _LOGGER.debug("⏱️ Таймаут обработки рекламных пакетов (истекло время сканирования)")
        except Exception as err:
            _LOGGER.error(f"❌ Ошибка обработки рекламных пакетов: {err}", exc_info=True)

    def _process_device_sync(self, service_info: BluetoothServiceInfoBleak) -> bool:
        """Synchronously process a device."""
        if not self._is_elehant_device(service_info):
            return False

        # Extract device data
        device_id = self._extract_device_id(service_info)
        if not device_id:
            _LOGGER.debug(f"⚠️ Не удалось извлечь ID из устройства {service_info.address}")
            return False

        if device_id not in self.devices:
            _LOGGER.debug(f"⚠️ Устройство с ID {device_id} не найдено в конфигурации")
            return False

        # Parse the advertisement data
        data = self._parse_advertisement_data(service_info)
        if data:
            _LOGGER.info(f"✅ Получены данные от устройства {device_id}: {data}")
            
            # Update all sensors for this device
            main_sensor = self.devices.get(device_id)
            if main_sensor and isinstance(main_sensor, ElehantCounterSensor):
                main_sensor._handle_update(data)

            temp_sensor = self.devices.get(f"{device_id}_temp")
            if temp_sensor and isinstance(temp_sensor, ElehantTemperatureSensor):
                temp_sensor._handle_update(data)
        else:
            _LOGGER.debug(f"⚠️ Не удалось распарсить данные от {device_id}")

        return True

    async def _process_device(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Process a discovered device."""
        self._process_device_sync(service_info)

    def _is_elehant_device(self, service_info: BluetoothServiceInfoBleak) -> bool:
        """Check if the device is an Elehant sensor."""
        _LOGGER.debug(f"🔎 Проверка устройства: {service_info.address}, имя: {service_info.name}, UUIDs: {service_info.service_uuids}")
        
        # Check service UUID
        if ELEHANT_SERVICE_UUID in service_info.service_uuids:
            _LOGGER.info(f"✅ Elehant устройство обнаружено по UUID: {service_info.address}")
            return True

        # Check manufacturer data
        if service_info.manufacturer_data:
            _LOGGER.debug(f"   Manufacturer data: {service_info.manufacturer_data}")
            if ELEHANT_MANUFACTURER_ID in service_info.manufacturer_data:
                mfg_data = service_info.manufacturer_data[ELEHANT_MANUFACTURER_ID]
                _LOGGER.info(f"✅ Elehant устройство обнаружено по manufacturer ID: {service_info.address}")
                _LOGGER.debug(f"   Manufacturer data hex: {mfg_data.hex()}")
                return True

        # Check device name
        if service_info.name and "ELEHANT" in service_info.name.upper():
            _LOGGER.info(f"✅ Elehant устройство обнаружено по имени: {service_info.name}")
            return True

        return False

    def _extract_device_id(self, service_info: BluetoothServiceInfoBleak) -> str | None:
        """Extract device ID from advertisement data."""
        # Try to extract from manufacturer data
        if service_info.manufacturer_data and ELEHANT_MANUFACTURER_ID in service_info.manufacturer_data:
            mfg_data = service_info.manufacturer_data[ELEHANT_MANUFACTURER_ID]
            if len(mfg_data) >= 4:
                device_id = int.from_bytes(mfg_data[0:4], byteorder="little")
                _LOGGER.debug(f"📟 ID из manufacturer data: {device_id}")
                return str(device_id)

        # Try to extract from service data
        for uuid, data in service_info.service_data.items():
            if ELEHANT_SERVICE_UUID in uuid:
                if len(data) >= 4:
                    device_id = int.from_bytes(data[0:4], byteorder="little")
                    _LOGGER.debug(f"📟 ID из service data: {device_id}")
                    return str(device_id)

        # Fallback to MAC address
        if service_info.address:
            _LOGGER.debug(f"📟 Используем MAC как ID: {service_info.address}")
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
            _LOGGER.debug(f"📦 Manufacturer data ({len(mfg_data)} байт): {mfg_data.hex()}")
            
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
                _LOGGER.debug(f"📦 Service data ({len(srv_data)} байт): {srv_data.hex()}")
                data["counter"] = int.from_bytes(srv_data[4:8], byteorder="little")
                if len(srv_data) >= 9:
                    data["battery"] = srv_data[8]
                if len(srv_data) >= 12:
                    temp_raw = int.from_bytes(srv_data[10:12], byteorder="little", signed=True)
                    data["temperature"] = temp_raw / 10.0
                break

        if "counter" in data:
            return data
        else:
            _LOGGER.debug(f"⚠️ Не найдены данные счетчика в пакете от {service_info.address}")
            return None
