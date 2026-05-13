"""Global fixtures for DiUS_Powersensor integration."""

from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from custom_components.dius.models import ConnectionSnapshot
from custom_components.dius.models import DiusSnapshot

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
    """Skip UDP client startup."""
    with patch(
        "custom_components.dius.DiusApiClient.async_start",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""
    with patch(
        "custom_components.dius.DiusApiClient.async_get_data",
        new=AsyncMock(
            return_value=DiusSnapshot(
                devices={},
                connection=ConnectionSnapshot(state="subscribed"),
                counters={},
            )
        ),
    ):
        yield


@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.dius.DiusApiClient.async_get_data",
        new=AsyncMock(side_effect=Exception),
    ):
        yield
