"""Constants for Elehant Water integration."""
from homeassistant.const import Platform

DOMAIN = "elehant_water"
PLATFORMS = [Platform.SENSOR]

# Configuration
CONF_DEVICES = "devices"
CONF_MEASUREMENT_WATER = "measurement_water"
CONF_MEASUREMENT_GAS = "measurement_gas"
CONF_SCAN_DURATION = "scan_duration"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_WATER_TYPE = "water_type"
CONF_NAME_TEMP = "name_temp"

# Default values
DEFAULT_SCAN_DURATION = 10
DEFAULT_SCAN_INTERVAL = 600
DEFAULT_MEASUREMENT_WATER = "m3"
DEFAULT_MEASUREMENT_GAS = "m3"

# Device types
DEVICE_TYPE_WATER = "water"
DEVICE_TYPE_GAS = "gas"

# Water types
WATER_TYPE_HOT = "hot"
WATER_TYPE_COLD = "cold"

# Measurement units
MEASUREMENT_LITERS = "l"
MEASUREMENT_CUBIC_METERS = "m3"

# Attributes
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_RSSI = "rssi"
ATTR_TEMPERATURE = "temperature"
ATTR_LAST_SEEN = "last_seen"
ATTR_COUNTER_VALUE = "counter_value"
