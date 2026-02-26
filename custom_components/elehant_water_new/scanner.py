"""Bluetooth scanner for Elehant water meters."""

import asyncio
import logging
from struct import unpack
from typing import Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DEVICE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    EXPECTED_FIRST_BYTE,
    IDX_BATTERY,
    IDX_COUNTER_START,
    IDX_SERIAL_START,
    IDX_TEMP_START,
)

_LOGGER = logging.getLogger(__name__)


def extract_serial_from_mac(mac: str) -> Optional[str]:
    """Extract potential serial number from the last 3 bytes of MAC address."""
    try:
        parts = mac.split(":")
        if len(parts) != 6:
            return None
        # Take bytes 3,4,5 (0-indexed) -> indices 3,4,5
        last_three = parts[3:6]
        # Convert hex string like '8B' to int, then to str. Form a single number string.
        # Example: ['01', '8B', '8B'] -> "1-139-139" or just "1139139"? Let's join as string.
        # Simpler: treat as a single hex number? Original code used it as a string "018B8B".
        # We'll convert to an integer string to compare with user input (which is decimal).
        # User inputs "11225" (decimal). MAC gives "018B8B" (hex) -> decimal 101259? Not match.
        # So we must treat the MAC part as a decimal representation of the hex bytes.
        # Example: 0x01, 0x8B, 0x8B as a 3-byte number = 0x018B8B = 101259. This doesn't match 11225.
        # BUT in Zud71's parser, serial is 3 bytes from packet: e.g., 0x00,0x2B,0xC1 = 11201.
        # So the serial is stored as a 3-byte integer. The MAC's last 3 bytes should be the SAME 3-byte integer.
        # So we need to interpret the last 3 MAC bytes as a 3-byte integer.
        serial_int = (int(parts[3], 16) << 16) + (int(parts[4], 16) << 8) + int(parts[5], 16)
        return str(serial_int)
    except (ValueError, IndexError) as err:
        _LOGGER.debug("Failed to extract serial from MAC %s: %s", mac, err)
        return None


def parse_elehant_data(data: bytes) -> Optional[dict]:
    """Parse manufacturer data from Elehant meter."""
    if len(data) < 16:  # Ensure enough data
        _LOGGER.debug("Data too short: %s", data.hex())
        return None

    # Check first byte
    if data[0] != EXPECTED_FIRST_BYTE:
        _LOGGER.debug("First byte mismatch: expected 0x%02X, got 0x%02X", EXPECTED_FIRST_BYTE, data[0])
        return None

    try:
        # Extract serial (3 bytes, big-endian)
        serial_bytes = data[IDX_SERIAL_START:IDX_SERIAL_START + 3]
        serial = int.from_bytes(serial_bytes, byteorder="big")

        # Extract counter (4 bytes, little-endian)
        counter_bytes = data[IDX_COUNTER_START:IDX_COUNTER_START + 4]
        # Value is in 0.1 units (liters if it's water)
        counter_raw = int.from_bytes(counter_bytes, byteorder="little")
        counter_value = counter_raw / 10.0

        # Battery (1 byte)
        battery = data[IDX_BATTERY]

        # Temperature (2 bytes, signed short, big-endian? Check Zud71: struct.unpack('>h', ...))
        temp_bytes = data[IDX_TEMP_START:IDX_TEMP_START + 2]
        temperature = unpack(">h", temp_bytes)[0] / 10.0

        return {
            "serial": str(serial),
            "counter_liters": counter_value,  # Always store base value in liters
            "battery": battery,
            "temperature": temperature,
        }
    except Exception as err:
        _LOGGER.error("Error parsing Elehant data: %s", err, exc_info=True)
        return None


class ElehantScanner:
    """Manages continuous BLE scanning for Elehant meters."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinators: dict[str, DataUpdateCoordinator],
        adapters: list[str],
        selected_adapter: Optional[str] = None,
    ):
        """Initialize scanner."""
        self.hass = hass
        self.coordinators = coordinators  # device_id -> coordinator
        self.adapters = adapters
        self.selected_adapter = selected_adapter
        self.scanner: Optional[BleakScanner] = None
        self._scan_task: Optional[asyncio.Task] = None

    async def async_start(self):
        """Start continuous scanning."""
        if self.scanner:
            _LOGGER.warning("Scanner already running")
            return

        _LOGGER.info("Starting Elehant scanner on adapter: %s", self.selected_adapter or "default")

        # Create scanner with callback
        self.scanner = BleakScanner(
            detection_callback=self._detection_callback,
            adapter=self.selected_adapter,  # Pass the selected adapter
        )

        # Start scanning in background task
        self._scan_task = self.hass.async_create_background_task(
            self._run_scanner(), "elehant_ble_scanner", eager_start=False
        )

    async def _run_scanner(self):
        """Run the scanner (in background)."""
        try:
            await self.scanner.start()
            _LOGGER.debug("BLE scanner started, waiting for devices...")
            # Keep scanner running indefinitely
            await asyncio.Event().wait()  # Sleep forever
        except asyncio.CancelledError:
            _LOGGER.info("Scanner task cancelled")
        except Exception as err:
            _LOGGER.error("Scanner error: %s", err, exc_info=True)
        finally:
            await self.scanner.stop()
            self.scanner = None
            _LOGGER.info("BLE scanner stopped")

    async def async_stop(self):
        """Stop scanning."""
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
            self._scan_task = None
        _LOGGER.info("Elehant scanner stopped")

    def _detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Process discovered BLE device."""
        # Level 1: Check manufacturer data
        if not advertisement_data.manufacturer_data:
            return

        # Check for expected first byte (simplified: assume any data with correct first byte)
        # Elehant manufacturer ID might be present but not guaranteed.
        # We'll just look at the first byte of any manufacturer data.
        for manuf_id, data in advertisement_data.manufacturer_data.items():
            if data and data[0] == EXPECTED_FIRST_BYTE:
                # Found potential Elehant packet
                _LOGGER.debug("Potential Elehant packet from MAC %s, manuf_id: 0x%04X, data: %s",
                              device.address, manuf_id, data.hex())
                self._process_packet(device.address, data)
                return  # Process only first matching manufacturer data
        # If no matching first byte, ignore

    def _process_packet(self, mac: str, data: bytes):
        """Process a packet that passed level 1."""
        # Level 2: Extract serial from MAC
        mac_serial = extract_serial_from_mac(mac)
        if not mac_serial:
            _LOGGER.debug("Could not extract serial from MAC %s", mac)
            return

        _LOGGER.debug("MAC %s -> extracted serial candidate: %s", mac, mac_serial)

        # Check if this serial corresponds to any configured device
        if mac_serial not in self.coordinators:
            _LOGGER.debug("Serial %s from MAC not in configured devices", mac_serial)
            return

        # Level 3: Parse data and verify serial
        parsed = parse_elehant_data(data)
        if not parsed:
            _LOGGER.debug("Failed to parse data for MAC %s", mac)
            return

        data_serial = parsed["serial"]
        if data_serial != mac_serial:
            _LOGGER.debug("Serial mismatch: MAC gave %s, data gave %s", mac_serial, data_serial)
            return

        # All checks passed! Update coordinator for this device
        coordinator = self.coordinators[mac_serial]
        # Get configured unit for this device from coordinator data (or config entry)
        # We'll pass the raw liters to coordinator; sensor will convert based on its unit setting.
        unit = coordinator.config_entry.data.get(CONF_UNIT_OF_MEASUREMENT)
        _LOGGER.info("Valid data for device %s (MAC %s): counter=%.1f L, battery=%d%%, temp=%.1f°C",
                     mac_serial, mac, parsed["counter_liters"], parsed["battery"], parsed["temperature"])

        # Update coordinator data
        coordinator.async_set_updated_data({
            "counter_liters": parsed["counter_liters"],
            "battery": parsed["battery"],
            "temperature": parsed["temperature"],
            "unit": unit,  # Pass unit so sensor knows
            "last_seen": coordinator.hass.loop.time(),
        })
