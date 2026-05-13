"""Tests for DiUS_Powersensor API and models."""

import json
from unittest.mock import AsyncMock

from custom_components.dius.api import DiusApiClient
from custom_components.dius.models import CONNECTION_EXPIRED
from custom_components.dius.models import CONNECTION_RECEIVING
from custom_components.dius.models import DEVICE_TYPE_PLUG
from custom_components.dius.models import DEVICE_TYPE_SENSOR
from custom_components.dius.models import normalize_instant_power_message


def test_normalize_sensor_converts_u_and_applies_offset():
    """Normalize sensor U readings to watts and apply sensor-only offset."""
    msg = {
        "mac": "2cf4320f48a2",
        "device": "sensor",
        "type": "instant_power",
        "unit": "U",
        "power": 193,
        "duration": 30,
        "starttime": 1000,
    }

    device = normalize_instant_power_message(msg, now=123, u_conv=19.3, w_adj=-5)

    assert device.mac == "2cf4320f48a2"
    assert device.device_type == DEVICE_TYPE_SENSOR
    assert device.power_w == 5
    assert device.duration_s == 30


def test_normalize_plug_does_not_apply_sensor_offset():
    """Normalize plug readings without applying sensor offset."""
    msg = {
        "mac": "2cf4320f48a2",
        "device": "plug",
        "type": "instant_power",
        "unit": "W",
        "power": 39,
    }

    device = normalize_instant_power_message(msg, now=123, u_conv=19.3, w_adj=-5)

    assert device.device_type == DEVICE_TYPE_PLUG
    assert device.power_w == 39


async def test_client_processes_valid_and_invalid_messages():
    """Process valid messages and count invalid payloads without crashing."""
    client = DiusApiClient("127.0.0.1", 49476)

    await client.process_message(b"not json")
    await client.process_message(json.dumps({"type": "instant_power"}).encode())
    await client.process_message(
        json.dumps(
            {
                "mac": "2cf4320f48a2",
                "device": "sensor",
                "type": "instant_power",
                "unit": "W",
                "power": 1200,
                "role": "solar",
            }
        ).encode()
    )

    snapshot = await client.async_get_data()
    assert len(snapshot.devices) == 1
    assert snapshot.counters["parse_errors"] == 1
    assert snapshot.counters["invalid_messages"] == 1
    assert snapshot.connection.state == CONNECTION_RECEIVING


async def test_subscription_warning_and_expiry_paths():
    """Warnings resubscribe and expiry triggers reconnect."""
    client = DiusApiClient("127.0.0.1", 49476)
    client.async_subscribe = AsyncMock(return_value=None)

    await client.process_message(json.dumps({"type": "subscription", "subtype": "warning"}))
    assert client.async_subscribe.await_count == 1

    await client.process_message(json.dumps({"type": "subscription", "subtype": "expiry"}))
    snapshot = await client.async_get_data()
    assert snapshot.connection.state == CONNECTION_EXPIRED
