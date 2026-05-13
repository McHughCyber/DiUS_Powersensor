"""Tests for DiUS_Powersensor sensor entities."""

import logging
from unittest.mock import AsyncMock
from unittest.mock import patch

from custom_components.dius.const import DOMAIN
from custom_components.dius.models import ConnectionSnapshot
from custom_components.dius.models import DiusSnapshot
from custom_components.dius.models import normalize_instant_power_message
from custom_components.dius.sensor import DiusEnergySensor
from custom_components.dius.sensor import DiusPowerSensor
from custom_components.dius.sensor import MAX_TRACKED_SAMPLES
from homeassistant.const import UnitOfEnergy
from homeassistant.const import UnitOfPower
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import MOCK_CONFIG


async def test_per_sensor_energy_entity_created_for_solar_sensor(hass):
    """Dynamically create per-MAC power and energy entities."""
    sensor_mac = "2cf4320f48a2"

    with patch(
        "custom_components.dius.DiusApiClient.async_start",
        AsyncMock(return_value=None),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG,
            entry_id="test_sensor",
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.api.process_message(
        b'{"mac":"2cf4320f48a2","device":"sensor","role":"solar",'
        b'"type":"instant_power","power":5,"unit":"W","duration":30,'
        b'"starttime":1774336795}'
    )
    await hass.async_block_till_done()

    sensor_states = hass.states.async_all("sensor")
    energy_state = next(
        (
            state
            for state in sensor_states
            if state.attributes.get("device_class") == "energy"
            and state.attributes.get("unit_of_measurement")
            == UnitOfEnergy.KILO_WATT_HOUR
        ),
        None,
    )
    power_state = next(
        (
            state
            for state in sensor_states
            if state.attributes.get("device_class") == "power"
            and state.attributes.get("unit_of_measurement") == UnitOfPower.WATT
            and state.attributes.get("mac") == sensor_mac
        ),
        None,
    )

    assert power_state is not None
    assert energy_state is not None
    assert energy_state.attributes.get("state_class") == "total_increasing"

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_energy_entity_accumulates_positive_solar_power(hass):
    """Prefer summation and avoid double-counting derived samples."""
    sensor_mac = "2cf4320f48a2"
    coordinator = DataUpdateCoordinator(
        hass,
        logger=logging.getLogger(__name__),
        name=DOMAIN,
        update_method=AsyncMock(return_value={}),
    )
    device = normalize_instant_power_message(
        {
            "mac": sensor_mac,
            "device": "sensor",
            "role": "solar",
            "type": "instant_power",
            "power": 1200,
            "unit": "W",
            "duration": 30,
            "starttime": 1000,
        },
        now=123,
        u_conv=19.3,
        w_adj=0,
    )
    coordinator.data = DiusSnapshot(
        devices={device.key: device},
        connection=ConnectionSnapshot(state="receiving"),
        counters={},
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, options={})
    entity = DiusEnergySensor(coordinator, config_entry, device)

    value_1 = entity.native_value
    assert value_1 == 0.01

    value_2 = entity.native_value
    assert value_2 == value_1

    device_with_summation = normalize_instant_power_message(
        {
            "mac": sensor_mac,
            "device": "sensor",
            "role": "solar",
            "type": "instant_power",
            "power": 1,
            "unit": "W",
            "duration": 30,
            "starttime": 1030,
            "summation": 2_500_000,
        },
        now=124,
        u_conv=19.3,
        w_adj=0,
    )
    coordinator.data = DiusSnapshot(
        devices={device_with_summation.key: device_with_summation},
        connection=ConnectionSnapshot(state="receiving"),
        counters={},
    )
    assert entity.native_value == 2.5


async def test_power_sensor_stale_device_unavailable(hass):
    """Mark stale devices unavailable."""
    device = normalize_instant_power_message(
        {
            "mac": "2cf4320f48a2",
            "device": "plug",
            "type": "instant_power",
            "power": 39,
            "unit": "W",
        },
        now=0,
        u_conv=19.3,
        w_adj=0,
    )
    coordinator = DataUpdateCoordinator(
        hass,
        logger=logging.getLogger(__name__),
        name=DOMAIN,
        update_method=AsyncMock(return_value={}),
    )
    coordinator.data = DiusSnapshot(
        devices={device.key: device},
        connection=ConnectionSnapshot(state="receiving"),
        counters={},
        stale_timeout_seconds=60,
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, options={})
    entity = DiusPowerSensor(coordinator, config_entry, device)

    assert entity.native_value == 39
    assert entity.available is False


async def test_energy_entity_sample_tracking_is_bounded(hass):
    """Keep deduplication sample tracking bounded in size."""
    sensor_mac = "2cf4320f48a2"
    coordinator = DataUpdateCoordinator(
        hass,
        logger=logging.getLogger(__name__),
        name=DOMAIN,
        update_method=AsyncMock(return_value={}),
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, options={})
    first_device = normalize_instant_power_message(
        {
            "mac": sensor_mac,
            "device": "sensor",
            "role": "solar",
            "type": "instant_power",
            "power": 1200,
            "unit": "W",
            "duration": 30,
            "starttime": 1000,
        },
        now=123,
        u_conv=19.3,
        w_adj=0,
    )
    coordinator.data = DiusSnapshot(
        devices={first_device.key: first_device},
        connection=ConnectionSnapshot(state="receiving"),
        counters={},
    )
    entity = DiusEnergySensor(coordinator, config_entry, first_device)

    for i in range(MAX_TRACKED_SAMPLES + 50):
        device = normalize_instant_power_message(
            {
                "mac": sensor_mac,
                "device": "sensor",
                "role": "solar",
                "type": "instant_power",
                "power": 1200,
                "unit": "W",
                "duration": 30,
                "starttime": 1000 + i,
            },
            now=123 + i,
            u_conv=19.3,
            w_adj=0,
        )
        coordinator.data = DiusSnapshot(
            devices={device.key: device},
            connection=ConnectionSnapshot(state="receiving"),
            counters={},
        )
        _ = entity.native_value

    assert len(entity._processed_samples) == MAX_TRACKED_SAMPLES
