"""Constants for the Elehant Water integration."""

from homeassistant.const import Platform

DOMAIN = "elehant_water_new"
PLATFORMS = [Platform.SENSOR]

# Configuration
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"
CONF_BLUETOOTH_ADAPTER = "bluetooth_adapter"

# Units
UNIT_CUBIC_METERS = "m³"
UNIT_LITERS = "L"

# Default values
DEFAULT_UNIT = UNIT_CUBIC_METERS
DEFAULT_SCAN_INTERVAL = 300  # Not used in new logic, kept for compatibility

# Manufacturer data parsing constants (based on Zud71/elehant_meter)
# Byte indexes (0-based)
IDX_DATA_LENGTH = 0          # Byte 0: Always 0x0E (14) for this device?
IDX_MANUFACTURER_ID = 1      # Bytes 1-2: Manufacturer ID (0x055B)
IDX_FLAGS = 3                # Byte 3: Flags? (0x00)
IDX_PAYLOAD_START = 4        # Byte 4: Start of actual payload? (0x0F?)
IDX_SERIAL_START = 6         # Bytes 6,7,8 (3 bytes): Serial number (e.g., 0x00,0x2B,0xC1 -> 11201)
IDX_SERIAL_LEN = 3
IDX_COUNTER_START = 9        # Bytes 9,10,11,12 (4 bytes): Counter value in 0.1 units (liters?)
IDX_COUNTER_LEN = 4
IDX_BATTERY = 13             # Byte 13: Battery level (0-100%)
IDX_TEMP_START = 14          # Bytes 14,15 (2 bytes): Temperature in Celsius * 10 (signed short)
IDX_TEMP_LEN = 2

# Expected first byte of manufacturer data
EXPECTED_FIRST_BYTE = 0x80

# Manufacturer ID (for reference, not used for filtering)
MANUFACTURER_ID_ELEHANT = 0x055B
