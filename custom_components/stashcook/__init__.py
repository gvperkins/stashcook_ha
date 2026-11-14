"""Stashcook meal planner integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant

from .coordinator import StashcookCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type StashcookConfigEntry = ConfigEntry[StashcookCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: StashcookConfigEntry) -> bool:
    coordinator = StashcookCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # During startup the calendar entity may not exist yet, so the first refresh has
    # no calendar data. Refresh again once Home Assistant has finished starting.
    if hass.state is not CoreState.running:

        async def _refresh_when_started(_event: Event) -> None:
            await coordinator.async_request_refresh()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _refresh_when_started)
    return True


async def _async_reload(hass: HomeAssistant, entry: StashcookConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StashcookConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
