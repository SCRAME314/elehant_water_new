"""Init for Elehant Water integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_COUNTERS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DATA_COORDINATOR,
    DATA_CONFIG,
    DATA_DEVICES,
    DATA_SCANNER,
    DOMAIN,
)
from .scanner import ElehantScanner

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elehant Water from a config entry."""
    # Инициализация данных в hass.data
    hass.data.setdefault(DOMAIN, {})
    
    # Сохраняем конфигурацию
    config = {
        CONF_COUNTERS: entry.data.get(CONF_COUNTERS, []),
    }
    
    # Добавляем опции
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, 
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CONFIG: config,
        DATA_DEVICES: {},  # Здесь будут храниться данные счетчиков {counter_id: {state, attributes}}
        DATA_SCANNER: None,
        DATA_COORDINATOR: None,
    }

    # Создаем сканер Bluetooth
    scanner = ElehantScanner(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id][DATA_SCANNER] = scanner

    # Создаем координатор для обновления данных
    async def async_update_data():
        """Update data from Bluetooth scanner."""
        return await scanner.async_update()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )
    
    hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR] = coordinator

    # Первое обновление данных
    await coordinator.async_config_entry_first_refresh()

    # Настраиваем платформы
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Останавливаем сканер
        scanner = hass.data[DOMAIN][entry.entry_id].get(DATA_SCANNER)
        if scanner:
            await scanner.async_stop()
        
        # Удаляем данные
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
