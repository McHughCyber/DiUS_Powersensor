"""Adds config flow for DiUS_Powersensor."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_HOST
from .const import CONF_PORT
from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DEFAULT_W_ADJ
from .const import DEFAULT_W_to_U
from .const import DOMAIN
from .const import MAIN_POWER
from .const import PLUG
from .const import U_CONV
from .const import W_ADJ


class DiusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for dius."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            else:
                self._errors["base"] = "auth"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DiusOptionsFlowHandler(config_entry)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=self._errors,
        )

    async def _test_credentials(self, host, port):
        """Return true if credentials is valid."""
        # try:
        #     client = DiusApiClient(host, port)
        #     await client.async_get_data()
        return True
        # except Exception:  # pylint: disable=broad-except
        #     pass
        # return False


class DiusOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for dius."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        # Get current data to see what devices are available
        # Check if domain exists in hass.data (may not exist if setup was bypassed in tests)
        if DOMAIN not in self.hass.data or self.config_entry.entry_id not in self.hass.data[DOMAIN]:
            # Fallback to old structure if coordinator doesn't exist
            sensors = {}
            plugs = {}
        else:
            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
            sensors = coordinator.data.get("sensors", {})
            plugs = coordinator.data.get("plugs", {})

        # Build dynamic schema
        schema_dict = {}

        # If we have the new multi-sensor structure
        if sensors or plugs:
            # Add options for each sensor
            for mac in sensors.keys():
                sensor_key = f"sensor_{mac}"
                sensor_name = f"Power Sensor {mac[-4:].upper()}"
                schema_dict[
                    vol.Required(sensor_key, default=self.options.get(sensor_key, True))
                ] = bool

            # Add options for each plug
            for mac in plugs.keys():
                plug_key = f"plug_{mac}"
                plug_name = f"Power Plug {mac[-4:].upper()}"
                schema_dict[
                    vol.Required(plug_key, default=self.options.get(plug_key, True))
                ] = bool

        # Fallback to old structure for backward compatibility
        else:
            schema_dict.update(
                {
                    vol.Required(
                        MAIN_POWER, default=self.options.get(MAIN_POWER, True)
                    ): bool,
                    vol.Required(PLUG, default=self.options.get(PLUG, True)): bool,
                }
            )

        # Add global conversion settings
        schema_dict.update(
            {
                vol.Required(
                    U_CONV, default=self.options.get(U_CONV, DEFAULT_W_to_U)
                ): vol.Coerce(float),
                vol.Required(
                    W_ADJ, default=self.options.get(W_ADJ, DEFAULT_W_ADJ)
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_HOST), data=self.options
        )
