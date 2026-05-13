"""Config flow for DiUS_Powersensor."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import async_probe_relay
from .const import CONF_HOST
from .const import CONF_PORT
from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DEFAULT_STALE_TIMEOUT_SECONDS
from .const import DEFAULT_W_ADJ
from .const import DEFAULT_W_to_U
from .const import DOMAIN
from .const import MAIN_POWER
from .const import PLUG
from .const import STALE_TIMEOUT_SECONDS
from .const import U_CONV
from .const import W_ADJ
from .models import entity_key

PROBE_TIMEOUT_SECONDS = 5


class DiusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for DiUS PowerSensor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            errors = await _validate_input(user_input)
            if not errors:
                unique_id = _entry_unique_id(user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )
            self._errors.update(errors)
            return self._show_config_form(user_input)

        return self._show_config_form(user_input)

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of an existing entry."""
        self._errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            errors = await _validate_input(user_input)
            if not errors:
                await self.async_set_unique_id(_entry_unique_id(user_input))
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )
            self._errors.update(errors)
            return self._show_config_form(user_input)

        return self._show_config_form(dict(entry.data))

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry):
        """Return options flow."""
        return DiusOptionsFlowHandler()

    def _show_config_form(self, user_input):
        """Show the configuration form."""
        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=user_input.get(CONF_HOST, DEFAULT_HOST),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=user_input.get(CONF_PORT, DEFAULT_PORT),
                    ): int,
                }
            ),
            errors=self._errors,
        )


class DiusOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for DiUS PowerSensor."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.options: dict[str, Any] = {}
        self._options_seeded = False

    def _ensure_options(self) -> None:
        """Copy current config entry options into the working dict once."""
        if not self._options_seeded:
            self.options = dict(self.config_entry.options)
            self._options_seeded = True

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle options."""
        self._ensure_options()
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(
                title=self.config_entry.data.get(CONF_HOST),
                data=self.options,
            )

        schema_dict: dict[Any, Any] = {}
        devices = self._known_devices()

        if devices:
            for device in devices:
                power_key = entity_key(device, "power")
                schema_dict[
                    vol.Required(power_key, default=self.options.get(power_key, True))
                ] = selector.BooleanSelector()

                energy_key = entity_key(device, "energy")
                if device.is_sensor and device.is_solar:
                    schema_dict[
                        vol.Required(
                            energy_key,
                            default=self.options.get(energy_key, True),
                        )
                    ] = selector.BooleanSelector()
        else:
            schema_dict.update(
                {
                    vol.Required(
                        MAIN_POWER,
                        default=self.options.get(MAIN_POWER, True),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        PLUG,
                        default=self.options.get(PLUG, True),
                    ): selector.BooleanSelector(),
                }
            )

        schema_dict.update(
            {
                vol.Required(
                    U_CONV,
                    default=self.options.get(U_CONV, DEFAULT_W_to_U),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=1000,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    W_ADJ,
                    default=self.options.get(W_ADJ, DEFAULT_W_ADJ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10000,
                        max=10000,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    STALE_TIMEOUT_SECONDS,
                    default=self.options.get(
                        STALE_TIMEOUT_SECONDS,
                        DEFAULT_STALE_TIMEOUT_SECONDS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60,
                        max=86400,
                        step=60,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
        )

    def _known_devices(self):
        """Return devices known by the active coordinator."""
        if (
            DOMAIN not in self.hass.data
            or self.config_entry.entry_id not in self.hass.data[DOMAIN]
        ):
            return []
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
        if not coordinator.data:
            return []
        return sorted(
            coordinator.data.devices.values(),
            key=lambda device: (device.device_type, device.mac),
        )


async def _validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input and return form errors."""
    host = user_input.get(CONF_HOST)
    try:
        port = int(user_input.get(CONF_PORT))
    except (TypeError, ValueError):
        return {"base": "invalid_host"}

    if not host or not isinstance(host, str) or not 0 < port <= 65535:
        return {"base": "invalid_host"}

    try:
        await async_probe_relay(host, port, timeout=PROBE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return {"base": "timeout"}
    except socket.gaierror:
        return {"base": "invalid_host"}
    except OSError:
        return {"base": "cannot_connect"}
    except Exception:  # pylint: disable=broad-except
        return {"base": "unknown"}
    return {}


def _entry_unique_id(data: dict[str, Any]) -> str:
    """Return the unique id for a relay endpoint."""
    return f"{data[CONF_HOST]}:{data[CONF_PORT]}"
