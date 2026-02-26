"""Config flow for Elehant Water integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_COUNTERS,
    CONF_COUNTER_ID,
    CONF_COUNTER_TYPE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    COUNTER_TYPE_WATER,
    COUNTER_TYPE_GAS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=3600)
        ),
    }
)

STEP_COUNTER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTER_ID): str,
        vol.Required(CONF_COUNTER_TYPE, default=COUNTER_TYPE_WATER): vol.In(
            {COUNTER_TYPE_WATER: "Water", COUNTER_TYPE_GAS: "Gas"}
        ),
        vol.Optional(CONF_NAME): str,
    }
)


class ElehantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elehant Water."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self.data = {
            CONF_COUNTERS: [],
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }
        self.current_counter = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.data[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            return await self.async_step_counter()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_counter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding counters."""
        errors = {}

        if user_input is not None:
            # Проверяем уникальность ID
            counter_id = user_input[CONF_COUNTER_ID]
            for counter in self.data[CONF_COUNTERS]:
                if counter[CONF_COUNTER_ID] == counter_id:
                    errors["base"] = "id_exists"
                    break
            else:
                # Добавляем счетчик
                counter_data = {
                    CONF_COUNTER_ID: counter_id,
                    CONF_COUNTER_TYPE: user_input[CONF_COUNTER_TYPE],
                }
                if CONF_NAME in user_input and user_input[CONF_NAME]:
                    counter_data[CONF_NAME] = user_input[CONF_NAME]
                
                self.data[CONF_COUNTERS].append(counter_data)

                # Спрашиваем, добавить еще счетчик
                return await self.async_step_counter_confirm()

        return self.async_show_form(
            step_id="counter", data_schema=STEP_COUNTER_SCHEMA, errors=errors
        )

    async def async_step_counter_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask to add another counter."""
        if user_input is not None:
            if user_input.get("add_another", False):
                return await self.async_step_counter()
            return self.async_create_entry(title="Elehant Water", data=self.data)

        return self.async_show_form(
            step_id="counter_confirm",
            data_schema=vol.Schema(
                {vol.Optional("add_another", default=False): bool}
            ),
        )
