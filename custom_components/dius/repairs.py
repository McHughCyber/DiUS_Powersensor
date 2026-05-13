"""Repair issue helpers for DiUS PowerSensor."""

from __future__ import annotations

import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .const import U_CONV
from .models import CONNECTION_FAILED
from .models import CONNECTION_RECONNECTING

NO_DEVICES_GRACE_SECONDS = 300
RECONNECT_REPAIR_THRESHOLD = 3

ISSUE_RELAY_UNREACHABLE = "relay_unreachable"
ISSUE_NO_DEVICES = "no_devices_discovered"
ISSUE_INVALID_CONVERSION = "invalid_conversion"


async def async_update_issues(hass: HomeAssistant, entry, snapshot, setup_time: float) -> None:
    """Create or clear repair issues for current integration health."""
    if entry.options.get(U_CONV, 19.3) <= 0:
        _create_issue(hass, ISSUE_INVALID_CONVERSION, "invalid_conversion")
    else:
        _delete_issue(hass, ISSUE_INVALID_CONVERSION)

    if (
        snapshot.connection.state in {CONNECTION_FAILED, CONNECTION_RECONNECTING}
        and snapshot.connection.reconnects >= RECONNECT_REPAIR_THRESHOLD
    ):
        _create_issue(hass, ISSUE_RELAY_UNREACHABLE, "relay_unreachable")
    else:
        _delete_issue(hass, ISSUE_RELAY_UNREACHABLE)

    if not snapshot.devices and time.time() - setup_time > NO_DEVICES_GRACE_SECONDS:
        _create_issue(hass, ISSUE_NO_DEVICES, "no_devices_discovered")
    else:
        _delete_issue(hass, ISSUE_NO_DEVICES)


def _create_issue(hass: HomeAssistant, issue_id: str, translation_key: str) -> None:
    """Create a repair issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
    )


def _delete_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Delete a repair issue if present."""
    ir.async_delete_issue(hass, DOMAIN, issue_id)
