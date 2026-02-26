"""Config flow for Elehant Water integration."""

import logging
import voluptuous as vol

from bleak import get_adapters
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_BLUETOOTH_ADAPTER,
    DEFAULT_UNIT,
    DOMAIN,
    UNIT_CUBIC_METERS,
    UNIT_LITERS,
)

_LOGGER = logging.getLogger(__name__)


class ElehantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elehant Water."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            # Validate device ID (should be numeric, at least 3 digits)
            if not device_id.isdigit():
                errors[CONF_DEVICE_ID] = "invalid_id"
            else:
                # Check if already configured
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                # Proceed to options? Or create entry directly.
                # We'll create entry now and let user configure units later.
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE_NAME],
                    data={
                        CONF_DEVICE_ID: device_id,
                        CONF_DEVICE_NAME: user_input[CONF_DEVICE_NAME],
                    },
                )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): str,
                    vol.Required(CONF_DEVICE_NAME, default="Elehant Meter"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ElehantOptionsFlow(config_entry)


class ElehantOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_unit = self.config_entry.options.get(
            CONF_UNIT_OF_MEASUREMENT,
            self.config_entry.data.get(CONF_UNIT_OF_MEASUREMENT, DEFAULT_UNIT)
        )
        current_adapter = self.config_entry.options.get(
            CONF_BLUETOOTH_ADAPTER,
            self.config_entry.data.get(CONF_BLUETOOTH_ADAPTER)
        )

        # Get available Bluetooth adapters
        adapters = await get_adapters()
        adapter_names = [adapter.name for adapter in adapters if adapter.name]
        adapter_names.insert(0, "")  # Empty option for default

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UNIT_OF_MEASUREMENT,
                        default=current_unit,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[UNIT_CUBIC_METERS, UNIT_LITERS],
                            translation_key="unit_of_measurement",
                        )
                    ),
                    vol.Optional(
                        CONF_BLUETOOTH_ADAPTER,
                        description={"suggested_value": current_adapter},
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=adapter_names,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="bluetooth_adapter",
                        )
                    ),
                }
            ),
        )
