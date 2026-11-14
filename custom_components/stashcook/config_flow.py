"""Config flow for Stashcook."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .api import StashcookAuthError, StashcookClient
from .const import (
    CONF_CALENDAR,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CALENDAR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _clean_token(value: str) -> str:
    """Accept the bare value or a pasted "refreshToken=...; Path=/" cookie string."""
    value = value.strip().strip('"')
    if value.lower().startswith("refreshtoken="):
        value = value.split("=", 1)[1]
    return value.split(";")[0].strip()


async def _validate(hass: HomeAssistant, token: str) -> str | None:
    client = StashcookClient(hass, token)
    try:
        await client.async_refresh_access_token()
    except StashcookAuthError:
        return "invalid_token"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Stashcook validation failed")
        return "cannot_connect"
    return None


class StashcookConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = _clean_token(user_input[CONF_REFRESH_TOKEN])
            error = await _validate(self.hass, token)
            if not error:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Stashcook",
                    data={CONF_REFRESH_TOKEN: token},
                    options={
                        CONF_UPDATE_INTERVAL: user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                        CONF_CALENDAR: user_input.get(CONF_CALENDAR, DEFAULT_CALENDAR),
                    },
                )
            errors[CONF_REFRESH_TOKEN] = error

        schema = vol.Schema({
            vol.Required(CONF_REFRESH_TOKEN): TOKEN_SELECTOR,
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=1440)
            ),
            vol.Optional(CONF_CALENDAR, default=DEFAULT_CALENDAR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar")
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = _clean_token(user_input[CONF_REFRESH_TOKEN])
            error = await _validate(self.hass, token)
            if not error:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_REFRESH_TOKEN: token}
                )
            errors[CONF_REFRESH_TOKEN] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_REFRESH_TOKEN): TOKEN_SELECTOR}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StashcookOptionsFlow()


class StashcookOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        data = self.config_entry.data
        schema = vol.Schema({
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=opts.get(CONF_UPDATE_INTERVAL, data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
            vol.Optional(CONF_CALENDAR, default=opts.get(CONF_CALENDAR, DEFAULT_CALENDAR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar")
            ),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
