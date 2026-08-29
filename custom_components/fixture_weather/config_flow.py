"""Config flow for Fixture Weather."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_BASE_LOCATION, CONF_CALENDAR, DOMAIN


class FixtureWeatherConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a Fixture Weather config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial setup."""
        if user_input is not None:
            name = user_input["name"].strip()
            base_location = user_input[CONF_BASE_LOCATION].strip()

            await self.async_set_unique_id(
                f"{name.lower()}:{base_location.lower()}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required("name"): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT,
                    )
                ),
                vol.Required(CONF_BASE_LOCATION): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT,
                    )
                ),
                vol.Optional(CONF_CALENDAR): EntitySelector(
                    EntitySelectorConfig(
                        domain="calendar",
                        multiple=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
