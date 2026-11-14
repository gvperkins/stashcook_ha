"""Stashcook meal planner integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import StashcookCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type StashcookConfigEntry = ConfigEntry[StashcookCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: StashcookConfigEntry) -> bool:
    coordinator = StashcookCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: StashcookConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StashcookConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
