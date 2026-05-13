"""
Custom integration to integrate DiUS_Powersensor with Home Assistant.

For more details about this integration, please refer to
https://github.com/McHughCyber/DiUS_Powersensor
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import DiusApiClient
from .const import CONF_HOST
from .const import CONF_PORT
from .const import DEFAULT_STALE_TIMEOUT_SECONDS
from .const import DEFAULT_W_ADJ
from .const import DEFAULT_W_to_U
from .const import DOMAIN
from .const import PLATFORMS
from .const import STALE_TIMEOUT_SECONDS
from .const import STARTUP_MESSAGE
from .const import U_CONV
from .const import W_ADJ
from .models import DiusSnapshot
from .repairs import async_update_issues

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT)
    options = _options_with_defaults(entry)

    client = DiusApiClient(
        host,
        port,
        u_conv=options[U_CONV],
        w_adj=options[W_ADJ],
        stale_timeout_seconds=options[STALE_TIMEOUT_SECONDS],
    )
    await client.async_start()

    coordinator = DiusDataUpdateCoordinator(hass, entry, client=client)
    remove_client_listener = client.async_add_listener(coordinator.async_set_updated_data)
    entry.async_on_unload(remove_client_listener)

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not entry.options:
        hass.config_entries.async_update_entry(entry, options=options)

    for platform in PLATFORMS:
        coordinator.platforms.append(platform)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


def _options_with_defaults(entry: ConfigEntry) -> dict:
    """Return options including defaults."""
    return {
        U_CONV: entry.options.get(U_CONV, DEFAULT_W_to_U),
        W_ADJ: entry.options.get(W_ADJ, DEFAULT_W_ADJ),
        STALE_TIMEOUT_SECONDS: entry.options.get(
            STALE_TIMEOUT_SECONDS,
            DEFAULT_STALE_TIMEOUT_SECONDS,
        ),
        **dict(entry.options),
    }


class DiusDataUpdateCoordinator(DataUpdateCoordinator[DiusSnapshot]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: DiusApiClient,
    ) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []
        self.config_entry = config_entry
        self._setup_time = time.time()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            update_method=self.async_update_data,
        )

    async def async_update_data(self) -> DiusSnapshot:
        """Update data via library."""
        try:
            snapshot = await self.api.async_get_data()
            await async_update_issues(
                self.hass,
                self.config_entry,
                snapshot,
                self._setup_time,
            )
            return snapshot
        except Exception as exception:
            raise UpdateFailed() from exception

    def async_set_updated_data(self) -> None:
        """Push client updates into the coordinator."""
        super().async_set_updated_data(self.api.snapshot)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.api.async_stop()
    await coordinator.async_shutdown()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
