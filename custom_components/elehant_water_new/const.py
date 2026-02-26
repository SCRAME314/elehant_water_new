"""Constants for the Elehant Water integration."""

DOMAIN = "elehant_water_new"

# Конфигурация
CONF_COUNTERS = "counters"
CONF_COUNTER_ID = "counter_id"
CONF_COUNTER_TYPE = "counter_type"
CONF_NAME = "name"

# Типы счетчиков
COUNTER_TYPE_WATER = "water"
COUNTER_TYPE_GAS = "gas"

# Опции
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60

# MAC-маски для определения производителя и типа устройства
# Счетчики воды СГБТ (газ?) / Возможно газовые счетчики
MAC_MASK_GAS = [
    'b0:10:01',
    'b0:11:01',
    'b0:12:01',
    'b0:32:01',
    'b0:42:01'
]

# Счетчики воды СВД (с температурой)
MAC_MASK_WATER_TEMP = [
    'b0:01:02',
    'b0:02:02'
]

# Счетчики воды СВТ (двухтарифные)
MAC_MASK_WATER_DUAL = [
    'b0:03:02',
    'b0:04:02',
    'b0:05:02',
    'b0:06:02'
]

# Все маски для воды (для удобства проверки)
MAC_MASK_WATER = MAC_MASK_WATER_TEMP + MAC_MASK_WATER_DUAL

# Ключи для хранения данных в hass.data
DATA_COORDINATOR = "coordinator"
DATA_CONFIG = "config"
DATA_DEVICES = "devices"
DATA_SCANNER = "scanner"

# Атрибуты сенсоров
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_RSSI = "rssi"
ATTR_COUNTER_TYPE = "counter_type"
ATTR_LAST_SEEN = "last_seen"
ATTR_TEMPERATURE = "temperature"  # для СВД
ATTR_TARIFF_1 = "tariff_1"  # для двухтарифных
ATTR_TARIFF_2 = "tariff_2"  # для двухтарифных
ATTR_CURRENT_TARIFF = "current_tariff"  # текущий активный тариф
