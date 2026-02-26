"""Init for Elehant Water integration."""

import asyncio
import logging

from bleak import BleakScanner
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN, PLATFORMS
from .scanner import ElehantScanner

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elehant Water from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    device_id = entry.data[CONF_DEVICE_ID]
    device_name = entry.data[CONF_DEVICE_NAME]

    # Create coordinator for this device
    async def async_update_data():
        # This function is not used for polling; data comes from scanner.
        # But coordinator needs a method; we'll raise if no data yet.
        coordinator = hass.data[DOMAIN][device_id]
        if coordinator.data:
            return coordinator.data
        raise UpdateFailed("No data from device yet")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Elehant {device_name}",
        update_method=async_update_data,
        # No update_interval - we push updates from scanner
    )
    coordinator.config_entry = entry  # Store entry for access in scanner
    hass.data[DOMAIN][device_id] = coordinator

    # Register device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer="Elehant",
        model="Water Meter",
        sw_version="1.0",
    )

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start the global scanner if not already running
    if "scanner" not in hass.data[DOMAIN]:
        # Get available adapters using BleakScanner.discover with timeout 0
        # This is a workaround since get_adapters might not be available
        adapters = []
        try:
            # Try to get adapters through BleakScanner
            scanner = BleakScanner()
            adapter = getattr(scanner, "adapter", None)
            if adapter:
                adapters = [adapter]
            else:
                # On some platforms, we might not get adapter info
                adapters = ["hci0", "hci1"]  # Common Linux adapter names
        except Exception as err:
            _LOGGER.warning("Could not get Bluetooth adapters: %s", err)
            adapters = ["default"]
        
        adapter_names = adapters
        # Get selected adapter from config entry options (first device sets the scanner)
        selected_adapter = entry.options.get("bluetooth_adapter") or entry.data.get("bluetooth_adapter")
        if selected_adapter and selected_adapter not in adapter_names:
            _LOGGER.warning("Selected adapter %s not found, using default", selected_adapter)
            selected_adapter = None

        # Create scanner, passing all coordinators for lookup
        scanner = ElehantScanner(
            hass,
            hass.data[DOMAIN],  # dict of device_id -> coordinator
            adapter_names,
            selected_adapter
        )
        hass.data[DOMAIN]["scanner"] = scanner
        await scanner.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device_id = entry.data[CONF_DEVICE_ID]
    coordinator = hass.data[DOMAIN].pop(device_id, None)

    # Forward unload to platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # If no more devices, stop scanner
    if unload_ok and len(hass.data[DOMAIN]) == 1:  # Only "scanner" left
        scanner = hass.data[DOMAIN].pop("scanner", None)
        if scanner:
            await scanner.async_stop()

    return unload_ok
