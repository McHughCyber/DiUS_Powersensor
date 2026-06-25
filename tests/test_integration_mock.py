"""Integration tests against the mock Powersensor server."""

from __future__ import annotations

import asyncio
import json
import socket
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from custom_components.dius.api import DiusApiClient
from custom_components.dius.const import DOMAIN
from homeassistant.const import UnitOfPower
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import MOCK_INTEGRATION_CONFIG
from .const import MOCK_INTEGRATION_OPTIONS

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "powersensor_messages.json"

HOUSE_SENSOR_MAC = "2cf4320f292a"
SOLAR_SENSOR_MAC = "2cf4320f48a2"
PLUG_MAC = "a4cf1276fc70"
ENTITY_MAC_SUFFIXES = (
    HOUSE_SENSOR_MAC[-4:],
    SOLAR_SENSOR_MAC[-4:],
    PLUG_MAC[-4:],
)
_REAL_ASYNCIO_SLEEP = asyncio.sleep


def _load_fixture() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _subscribe_and_collect(
    host: str,
    port: int,
    duration: float,
) -> list[dict]:
    """Subscribe to the mock server and return decoded JSON messages."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    sock.connect((host, port))
    sock.send(b"subscribe(180)\n")

    messages: list[dict] = []
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        try:
            raw = sock.recv(4096)
        except TimeoutError:
            continue
        messages.append(json.loads(raw.decode("utf-8")))
    sock.close()
    return messages


async def _wait_for_client_data(
    client: DiusApiClient,
    *,
    timeout: float = 12.0,
) -> dict:
    """Wait until the client has received all expected device MACs."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = await client.async_get_data()
        if (
            HOUSE_SENSOR_MAC in data["sensors"]
            and SOLAR_SENSOR_MAC in data["sensors"]
            and PLUG_MAC in data["plugs"]
        ):
            return data
        await asyncio.sleep(0.5)
    return await client.async_get_data()


async def _allow_discovery_before_entity_setup(seconds: float) -> None:
    """Match async_setup_entry's initial wait so all device types are discovered."""
    if seconds == 2:
        seconds = 12.0
    await _REAL_ASYNCIO_SLEEP(seconds)


@pytest.mark.integration
def test_mock_server_requires_subscribe(mock_powersensor_server):
    """The mock server only emits traffic after a subscribe request."""
    host = mock_powersensor_server["host"]
    port = mock_powersensor_server["port"]

    idle_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    idle_sock.settimeout(0.3)
    idle_sock.bind((host, 0))
    with pytest.raises(TimeoutError):
        idle_sock.recvfrom(4096)
    idle_sock.close()

    messages = _subscribe_and_collect(host, port, duration=2.5)
    assert messages, "expected traffic after subscribe"


@pytest.mark.integration
def test_mock_payload_shapes_match_capture(mock_powersensor_server):
    """Mock messages include the fields observed on a live gateway."""
    fixture = _load_fixture()
    messages = _subscribe_and_collect(
        mock_powersensor_server["host"],
        mock_powersensor_server["port"],
        duration=2.5,
    )

    sensors = [m for m in messages if m.get("device") == "sensor"]
    plugs = [m for m in messages if m.get("device") == "plug"]
    assert sensors, "expected sensor instant_power messages"
    assert plugs, "expected plug instant_power messages"

    house_sensor = next(m for m in sensors if m.get("role") == "house-net")
    solar_sensor = next(m for m in sensors if m.get("role") == "solar")
    plug = plugs[0]

    for sample, live in (
        (house_sensor, fixture["sensor_house_net"]),
        (solar_sensor, fixture["sensor_solar"]),
        (plug, fixture["plug"]),
    ):
        assert set(sample.keys()) == set(live.keys())
        assert sample["type"] == "instant_power"
        assert sample["device"] == live["device"]


@pytest.mark.integration
async def test_api_client_receives_mock_traffic(
    mock_powersensor_server, socket_enabled
):
    """DiusApiClient stores sensor and plug readings from the mock server."""
    host = mock_powersensor_server["host"]
    port = mock_powersensor_server["port"]

    client = await DiusApiClient.start(host, port)
    try:
        data = await _wait_for_client_data(client)
    finally:
        await client.stop()

    assert data["sensors"], "expected at least one sensor MAC"
    assert data["plugs"], "expected at least one plug MAC"
    assert HOUSE_SENSOR_MAC in data["sensors"]
    assert SOLAR_SENSOR_MAC in data["sensors"]
    assert PLUG_MAC in data["plugs"]

    house = data["sensors"][HOUSE_SENSOR_MAC]
    assert house["unit"] == "w"
    assert house["role"] == "house-net"
    assert isinstance(house["power"], int)

    plug = data["plugs"][PLUG_MAC]
    assert plug["unit"] == "W"
    assert plug["source"] == "BLE"


@pytest.mark.integration
async def test_integration_setup_creates_entities(
    hass,
    mock_powersensor_server,
    socket_enabled,
):
    """Home Assistant creates per-MAC power entities from the mock server."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_INTEGRATION_CONFIG,
        options=MOCK_INTEGRATION_OPTIONS,
        entry_id="integration_mock",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.dius.asyncio.sleep",
        side_effect=_allow_discovery_before_entity_setup,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    states = {state.entity_id: state for state in hass.states.async_all("sensor")}
    for suffix in ENTITY_MAC_SUFFIXES:
        assert any(
            suffix in entity_id for entity_id in states
        ), f"expected an entity containing MAC suffix {suffix!r}, got {sorted(states)}"

    house_power = next(
        state
        for state in states.values()
        if state.attributes.get("device_class") == "power"
        and state.attributes.get("role") == "house-net"
    )
    assert house_power.state not in ("unknown", "unavailable")
    assert house_power.attributes.get("unit_of_measurement") == UnitOfPower.WATT

    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.integration
async def test_integration_sensor_cadence_is_slower_than_plug(
    mock_powersensor_server,
):
    """Sensor bursts arrive less frequently than plug samples, as on live hardware."""
    messages = _subscribe_and_collect(
        mock_powersensor_server["host"],
        mock_powersensor_server["port"],
        duration=3.0,
    )
    sensor_count = sum(1 for message in messages if message.get("device") == "sensor")
    plug_count = sum(1 for message in messages if message.get("device") == "plug")

    assert plug_count > sensor_count
    assert plug_count >= 5
