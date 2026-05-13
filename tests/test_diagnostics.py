"""Tests for integration diagnostics."""

from unittest.mock import MagicMock
from custom_components.dius.const import CONF_HOST
from custom_components.dius.const import CONF_PORT
from custom_components.dius.const import DOMAIN
from custom_components.dius.diagnostics import _mask_mac
from custom_components.dius.diagnostics import async_get_config_entry_diagnostics
from custom_components.dius.models import ConnectionSnapshot
from custom_components.dius.models import DiusDeviceData
from custom_components.dius.models import DiusSnapshot
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_config_entry_diagnostics(hass, skip_api_start):
    """Diagnostics redact MACs and expose connection metadata."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.99", CONF_PORT: 49476},
        options={},
    )
    entry.add_to_hass(hass)
    now = 1_700_000_000.0
    device = DiusDeviceData(
        key="sensor_aa",
        mac="112233445566",
        device_type="sensor",
        role="solar",
        power_w=100.0,
        unit="W",
        duration_s=60.0,
        starttime=None,
        summation=None,
        count=1,
        last_seen=now - 10.0,
        raw={"mac": "112233445566"},
    )
    snap = DiusSnapshot(
        devices={"sensor_aa": device},
        connection=ConnectionSnapshot(state="receiving"),
        counters={"instant_power": 5},
    )
    coordinator = MagicMock()
    coordinator.data = snap
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["connection"]["state"] == "receiving"
    assert diag["counters"]["instant_power"] == 5
    assert "sensor_aa" in diag["devices"]
    assert diag["devices"]["sensor_aa"]["mac"] == "**REDACTED**"
    assert "last_seen_age_seconds" in diag["devices"]["sensor_aa"]


def test_mask_mac():
    """MAC masking handles short and long identifiers."""
    assert _mask_mac("ab") == "****"
    assert _mask_mac("112233445566") == "****5566"
