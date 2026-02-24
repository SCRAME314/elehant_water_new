"""Config flow for Elehant Water integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_MEASUREMENT_WATER,
    CONF_MEASUREMENT_GAS,
    CONF_SCAN_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_WATER_TYPE,
    CONF_NAME_TEMP,
    DEFAULT_SCAN_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_MEASUREMENT_WATER,
    DEFAULT_MEASUREMENT_GAS,
    WATER_TYPE_HOT,
    WATER_TYPE_COLD,
    MEASUREMENT_LITERS,
    MEASUREMENT_CUBIC_METERS,
    DEVICE_TYPE_WATER,
    DEVICE_TYPE_GAS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_DURATION, default=DEFAULT_SCAN_DURATION): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=60, unit_of_measurement="seconds", mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10, max=3600, unit_of_measurement="seconds", mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_MEASUREMENT_WATER, default=DEFAULT_MEASUREMENT_WATER): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS],
                translation_key="measurement_water",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_MEASUREMENT_GAS, default=DEFAULT_MEASUREMENT_GAS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS],
                translation_key="measurement_gas",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)

STEP_ADD_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(CONF_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[DEVICE_TYPE_WATER, DEVICE_TYPE_GAS],
                translation_key="device_type",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_NAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_WATER_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[WATER_TYPE_HOT, WATER_TYPE_COLD],
                translation_key="water_type",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_NAME_TEMP): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
    }
)


class ElehantWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elehant Water."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self.data = user_input
        self.data[CONF_DEVICES] = []
        return await self.async_step_add_device()

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a device."""
        errors = {}

        if user_input is not None:
            # Validate device ID (basic check)
            device_id = user_input[CONF_ID]
            if not device_id or not str(device_id).strip():
                errors["base"] = "invalid_id"
            else:
                # Add device to the list
                self.devices.append(user_input)
                
                # Ask if user wants to add another device
                return await self.async_step_add_another()

        return self.async_show_form(
            step_id="add_device",
            data_schema=STEP_ADD_DEVICE_SCHEMA,
            errors=errors,
            description_placeholders={"device_number": str(len(self.devices) + 1)},
        )

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add another device."""
        if user_input is not None:
            if user_input.get("add_another", False):
                return await self.async_step_add_device()
            
            # Finish setup
            self.data[CONF_DEVICES] = self.devices
            return self.async_create_entry(
                title=f"Elehant Sensors ({len(self.devices)} devices)",
                data=self.data,
                options=self.data,  # 👈 ВОТ ЭТА СТРОКА - добавляем options для OptionsFlow
            )

        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema(
                {
                    vol.Required("add_another", default=False): selector.BooleanSelector(
                        selector.BooleanSelectorConfig()
                    ),
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return ElehantWaterOptionsFlow(config_entry)


class ElehantWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Elehant Water."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update scan parameters
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_DURATION,
                        default=self.config_entry.options.get(CONF_SCAN_DURATION, 
                                                             self.config_entry.data.get(CONF_SCAN_DURATION, DEFAULT_SCAN_DURATION)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=60, unit_of_measurement="seconds", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(CONF_SCAN_INTERVAL,
                                                              self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10, max=3600, unit_of_measurement="seconds", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
