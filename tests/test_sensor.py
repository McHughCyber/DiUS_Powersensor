"""Tests for DiUS_Powersensor sensor entities."""

import logging
from unittest.mock import AsyncMock
from unittest.mock import patch

from custom_components.dius.const import DOMAIN
from homeassistant.const import UnitOfEnergy
from homeassistant.const import UnitOfPower
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import MOCK_CONFIG


async def test_per_sensor_energy_entity_created_for_solar_sensor(hass):
    """Create per-MAC power and energy entities and validate metadata."""
    sensor_mac = "2cf4320f48a2"
    data = {
        "sensors": {
            sensor_mac: {
                "mac": sensor_mac,
                "device": "sensor",
                "role": "solar",
                "type": "instant_power",
                "power": 5,
                "unit": "w",
                "duration": 30,
                "starttime": 1774336795,
            }
        },
        "plugs": {},
        "reconnects": 0,
    }

    client = AsyncMock()
    client.async_get_data = AsyncMock(return_value=data)
    client.stop = AsyncMock(return_value=None)

    with patch(
        "custom_components.dius.DiusApiClient.start", AsyncMock(return_value=client)
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id="test_sensor"
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
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
        ),
        None,
    )

    assert power_state is not None
    assert energy_state is not None
    assert energy_state.attributes.get("state_class") == "total_increasing"

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_energy_entity_accumulates_positive_solar_power(hass):
    """Accumulate kWh from solar positive power samples only."""
    from custom_components.dius.sensor import DiusEnergySensor
    from custom_components.dius.sensor import DiusSensorDescription

    sensor_mac = "2cf4320f48a2"
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, options={})
    config_entry.add_to_hass(hass)
    coordinator = DataUpdateCoordinator(
        hass,
        logger=logging.getLogger(__name__),
        name=DOMAIN,
        config_entry=config_entry,
        update_method=AsyncMock(return_value={}),
    )
    coordinator.data = {
        "sensors": {
            sensor_mac: {
                "role": "solar",
                "power": 1200,
                "duration": 30,
                "starttime": 1000,
            }
        }
    }
    description = DiusSensorDescription(
        key=f"sensor_energy_{sensor_mac}",
        name="Power Sensor 48A2 Energy",
        measurement_type="energy",
    )
    entity = DiusEnergySensor(
        coordinator, config_entry, description, sensor_mac, "sensor"
    )

    value_1 = entity.native_value
    assert value_1 == 0.01

    coordinator.data["sensors"][sensor_mac]["power"] = 0
    value_2 = entity.native_value
    assert value_2 == value_1

    coordinator.data["sensors"][sensor_mac]["power"] = -100
    value_3 = entity.native_value
    assert value_3 == value_2
