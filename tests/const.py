"""Constants for DiUS_Powersensor tests."""

from custom_components.dius.const import (
    CONF_HOST,
)
from custom_components.dius.const import (
    CONF_PORT,
)

MOCK_CONFIG_API = {CONF_HOST: "127.0.0.1", CONF_PORT: 49476}
MOCK_CONFIG = {CONF_HOST: "192.168.1.1", CONF_PORT: 6789}
MOCK_OPTIONS = {"sensor": True, "plug": False, "U_conv": 32.1, "W_adj": -125}
MOCK_INTEGRATION_HOST = "127.0.0.1"
MOCK_INTEGRATION_PORT = 49476
MOCK_INTEGRATION_CONFIG = {
    CONF_HOST: MOCK_INTEGRATION_HOST,
    CONF_PORT: MOCK_INTEGRATION_PORT,
}
MOCK_INTEGRATION_OPTIONS = {
    "sensor_2cf4320f292a": True,
    "sensor_2cf4320f48a2": True,
    "sensor_energy_2cf4320f292a": True,
    "sensor_energy_2cf4320f48a2": True,
    "plug_a4cf1276fc70": True,
    "U_conv": 19.3,
    "W_adj": 0,
}
