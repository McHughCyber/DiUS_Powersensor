"""Global fixtures for DiUS_Powersensor integration."""

import json
import socket
import threading
import time
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from custom_components.dius.api import (
    DiusApiClient,
)

from .const import MOCK_INTEGRATION_HOST
from .const import MOCK_INTEGRATION_PORT

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


# This fixture, when used, will result in skipping calls to api.start.
@pytest.fixture(name="skip_api_start")
def skip_api_start(socket_enabled):
    """Skip start calls."""
    with patch(
        "custom_components.dius.DiusApiClient.start",
        return_value=DiusApiClient("127.0.0.1", 1234),
    ):
        yield


# This fixture, when used, will result in calls to async_get_data to return None. To have the call
# return a value, we would add the `return_value=<VALUE_TO_RETURN>` parameter to the patch call.
@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""
    with patch(
        "custom_components.dius.DiusApiClient.async_get_data",
        new_callable=AsyncMock,
        return_value={"sensors": {}, "plugs": {}, "reconnects": 0},
    ):
        yield


# In this fixture, we are forcing calls to async_get_data to raise an Exception. This is useful
# for exception handling.
@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.dius.DiusApiClient.async_get_data",
        new_callable=AsyncMock,
        side_effect=Exception,
    ), patch(
        "custom_components.dius.config_flow.DiusFlowHandler._test_credentials",
        return_value=False,
    ):
        yield


# In this fixture, we are forcing calls to async_get_data to raise an Exception. This is useful
# for exception handling.
@pytest.fixture(name="skip_socket_recv_sensor")
def skip_socket_sensor_fixture():
    """Simulate sensor data when retrieving data from API."""
    data = {
        "mac": "2cf4320aaaa",
        "device": "sensor",
        "summation": 21931891707,
        "duration": 30,
        "type": "instant_power",
        "batteryMicrovolt": 4143072,
        "unit": "U",
        "starttime": 1653477217,
        "power": 93184,
    }
    data = json.dumps(data).encode("utf-8")
    with patch(
        "socket.socket.recv",
        return_value=data,
    ):
        yield


def _port_is_open(host: str, port: int) -> bool:
    """Return True when something is already listening on host:port."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind((host, port))
    except OSError:
        return True
    finally:
        probe.close()
    return False


@pytest.fixture(scope="module")
def mock_powersensor_server():
    """Start the mock Powersensor server when it is not already running."""
    from tools.mock_powersensor import run_server

    host = MOCK_INTEGRATION_HOST
    port = MOCK_INTEGRATION_PORT
    started_here = False
    thread = None

    if not _port_is_open(host, port):
        thread = threading.Thread(
            target=run_server,
            kwargs={
                "host": host,
                "port": port,
                "plug_interval": 0.2,
                "sensor_interval": 1.0,
                "subscription_cycle": None,
            },
            daemon=True,
        )
        thread.start()
        started_here = True
        time.sleep(0.5)

    yield {"host": host, "port": port, "started_here": started_here}

    if started_here and thread is not None:
        # Daemon thread exits with the test process; nothing to tear down.
        pass
