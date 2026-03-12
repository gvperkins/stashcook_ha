
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from .const import DOMAIN, CONF_REFRESH_TOKEN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
from .coordinator import StashcookClient

class StashcookConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            refresh_token = user_input[CONF_REFRESH_TOKEN]
            client = StashcookClient(self.hass, refresh_token)
            try:
                await client.async_refresh_access_token()
            except Exception:
                errors[CONF_REFRESH_TOKEN] = "invalid_token"
            else:
                return self.async_create_entry(title="Stashcook", data={
                    CONF_REFRESH_TOKEN: refresh_token,
                    CONF_UPDATE_INTERVAL: user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                })

        schema = vol.Schema({
            vol.Required(CONF_REFRESH_TOKEN): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(int, vol.Range(min=5, max=1440)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

class StashcookOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Options updated", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(CONF_UPDATE_INTERVAL, default=self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): vol.All(int, vol.Range(min=5, max=1440)),
        })
        return self.async_show_form(step_id="init", data_schema=options_schema)

def async_get_options_flow(config_entry):
    return StashcookOptionsFlowHandler(config_entry)
