"""Diagnostics support for DiUS PowerSensor."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST
from .const import DOMAIN

TO_REDACT = {CONF_HOST, "raw"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    devices = {}
    now = time.time()

    if snapshot:
        for key, device in snapshot.devices.items():
            devices[key] = {
                **device.as_dict(include_raw=False),
                "mac": _mask_mac(device.mac),
                "last_seen_age_seconds": round(now - device.last_seen, 1),
            }

    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "connection": snapshot.connection.as_dict() if snapshot else None,
            "counters": dict(snapshot.counters) if snapshot else {},
            "devices": devices,
        },
        TO_REDACT,
    )


def _mask_mac(mac: str) -> str:
    """Return a partially masked MAC-like identifier."""
    if len(mac) <= 4:
        return "****"
    return f"****{mac[-4:]}"
