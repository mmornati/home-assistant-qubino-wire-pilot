"""Constants for the Qubino Wire Pilot integration."""

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.const import Platform

DOMAIN = "qubino_wire_pilot"
PLATFORMS = [Platform.CLIMATE]

DEFAULT_NAME = "Thermostat"

CONF_HEATER = "heater"
CONF_SENSOR = "sensor"
CONF_POWER_SENSOR = "power_sensor"
CONF_ADDITIONAL_MODES = "additional_modes"

# Configuration keys for custom percentage thresholds
CONF_VALUE_OFF = "value_off"
CONF_VALUE_FROST = "value_frost"
CONF_VALUE_ECO = "value_eco"
CONF_VALUE_COMFORT_2 = "value_comfort_2"
CONF_VALUE_COMFORT_1 = "value_comfort_1"
CONF_VALUE_COMFORT = "value_comfort"

PRESET_COMFORT_1 = "comfort-1"
PRESET_COMFORT_2 = "comfort-2"

# Default percentage thresholds (can be overridden in config). They follow
# the Qubino manual: 0-10 off, 11-20 frost, 21-30 eco, 31-40 comfort -2,
# 41-50 comfort -1, 51-99 comfort. Eco defaults to 25 because some devices
# only switch to eco from 25%.
DEFAULT_VALUE_OFF = 10
DEFAULT_VALUE_FROST = 20
DEFAULT_VALUE_ECO = 25
DEFAULT_VALUE_COMFORT_2 = 40
DEFAULT_VALUE_COMFORT_1 = 50
DEFAULT_VALUE_COMFORT = 99

# Power above which the radiator is considered to be heating (W)
POWER_HEATING_THRESHOLD = 5.0

# Pilot wire orders, from lowest to highest, with their threshold key and default
PILOT_ORDERS: list[tuple[str, str, int]] = [
    (PRESET_NONE, CONF_VALUE_OFF, DEFAULT_VALUE_OFF),
    (PRESET_AWAY, CONF_VALUE_FROST, DEFAULT_VALUE_FROST),
    (PRESET_ECO, CONF_VALUE_ECO, DEFAULT_VALUE_ECO),
    (PRESET_COMFORT_2, CONF_VALUE_COMFORT_2, DEFAULT_VALUE_COMFORT_2),
    (PRESET_COMFORT_1, CONF_VALUE_COMFORT_1, DEFAULT_VALUE_COMFORT_1),
    (PRESET_COMFORT, CONF_VALUE_COMFORT, DEFAULT_VALUE_COMFORT),
]
