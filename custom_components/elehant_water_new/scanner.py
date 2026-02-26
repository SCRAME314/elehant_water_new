"""Bluetooth scanner for Elehant devices."""
import asyncio
from collections import defaultdict
from datetime import datetime
import logging
import struct
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.core import HomeAssistant

from .const import (
    MAC_MASK_GAS,
    MAC_MASK_WATER,
    MAC_MASK_WATER_DUAL,
    MAC_MASK_WATER_TEMP,
    ATTR_BATTERY_LEVEL,
    ATTR_RSSI,
    ATTR_LAST_SEEN,
    ATTR_TEMPERATURE,
    ATTR_TARIFF_1,
    ATTR_TARIFF_2,
    ATTR_CURRENT_TARIFF,
)

_LOGGER = logging.getLogger(__name__)


class ElehantScanner:
    """Scanner for Elehant devices."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize scanner."""
        self.hass = hass
        self.entry_id = entry_id
        self._scanner = None
        self._scanning = False
        self._devices = defaultdict(dict)  # Временное хранилище найденных устройств

    async def async_update(self) -> dict[str, Any]:
        """Scan for devices and update data."""
        found_devices = {}
        
        def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
            """Callback for device detection."""
            if not advertisement_data or not advertisement_data.manufacturer_data:
                return
            
            mac = device.address.lower()
            
            # Проверяем, принадлежит ли устройство Elehant
            device_type = self._identify_device(mac)
            if not device_type:
                return
            
            # Парсим данные
            parsed_data = self._parse_advertisement_data(advertisement_data, device_type)
            if not parsed_data:
                return
            
            # Сохраняем во временное хранилище
            self._devices[mac] = {
                "name": device.name or f"Elehant {mac[-5:]}",
                "mac": mac,
                "device_type": device_type,
                "rssi": device.rssi,
                "last_seen": datetime.now(),
                **parsed_data
            }
            
            _LOGGER.debug(f"Found Elehant device: {mac}, type: {device_type}, data: {parsed_data}")

        # Запускаем сканирование на 10 секунд
        self._scanner = BleakScanner(detection_callback)
        await self._scanner.start()
        await asyncio.sleep(10)
        await self._scanner.stop()
        
        # Копируем найденные устройства
        found_devices = dict(self._devices)
        self._devices.clear()
        
        return found_devices

    def _identify_device(self, mac: str) -> str | None:
        """Identify device type by MAC address."""
        mac_lower = mac.lower()
        
        # Проверяем газовые счетчики
        for mask in MAC_MASK_GAS:
            if mask in mac_lower:
                return "gas"
        
        # Проверяем водяные счетчики с температурой
        for mask in MAC_MASK_WATER_TEMP:
            if mask in mac_lower:
                return "water_temp"
        
        # Проверяем двухтарифные водяные счетчики
        for mask in MAC_MASK_WATER_DUAL:
            if mask in mac_lower:
                return "water_dual"
        
        return None

    def _parse_advertisement_data(self, adv_data: AdvertisementData, device_type: str) -> dict | None:
        """Parse manufacturer specific data."""
        if not adv_data.manufacturer_data:
            return None
        
        # Берем первый (и обычно единственный) manufacturer data
        man_data = next(iter(adv_data.manufacturer_data.values()))
        
        try:
            # Парсим данные в зависимости от типа устройства
            if device_type == "gas":
                return self._parse_gas_data(man_data)
            elif device_type == "water_temp":
                return self._parse_water_temp_data(man_data)
            elif device_type == "water_dual":
                return self._parse_water_dual_data(man_data)
        except Exception as e:
            _LOGGER.error(f"Error parsing data for {device_type}: {e}")
        
        return None

    def _parse_gas_data(self, data: bytes) -> dict:
        """Parse gas counter data."""
        # Пример: СГБТ-1.8, СГБТ-3.2, СГБТ-4.0, СГБТ-4.0 ТК, СОНИК G4ТК
        # Структура из оригинального кода
        counter_num = int.from_bytes(data[6:9], byteorder='little')
        counter_count = int.from_bytes(data[9:13], byteorder='little')
        
        # Преобразование в зависимо от типа (в оригинале была логика для gas/water)
        # Скорее всего это показания в литрах, преобразуем в м³
        count = counter_count / 1000
        
        return {
            "counter_id": str(counter_num),
            "state": count,
            "battery_level": None,  # В оригинале не было
        }

    def _parse_water_temp_data(self, data: bytes) -> dict:
        """Parse water counter with temperature (СВД-15, СВД-20)."""
        # Структура из оригинального кода
        counter_num = int.from_bytes(data[6:9], byteorder='little')
        counter_count = int.from_bytes(data[9:13], byteorder='little')
        temperature = int.from_bytes(data[14:16], byteorder="little") / 100
        
        count = counter_count / 1000  # Преобразуем в м³
        
        return {
            "counter_id": str(counter_num),
            "state": count,
            ATTR_TEMPERATURE: temperature,
            "battery_level": None,
        }

    def _parse_water_dual_data(self, data: bytes) -> dict:
        """Parse dual-tariff water counter (СВТ-15, СВТ-20)."""
        # Структура из оригинального кода
        counter_num = int.from_bytes(data[6:9], byteorder='little')
        
        # Два тарифа
        tariff_1 = int.from_bytes(data[9:13], byteorder='little') / 1000
        tariff_2 = int.from_bytes(data[13:17], byteorder='little') / 1000
        
        # Текущий тариф (предположительно)
        current_tariff = data[17] if len(data) > 17 else 1
        
        return {
            "counter_id": str(counter_num),
            "state": tariff_1 + tariff_2,  # Общее показание
            ATTR_TARIFF_1: tariff_1,
            ATTR_TARIFF_2: tariff_2,
            ATTR_CURRENT_TARIFF: current_tariff,
            "battery_level": None,
        }

    async def async_stop(self):
        """Stop scanning."""
        if self._scanner and self._scanning:
            await self._scanner.stop()
            self._scanning = False
