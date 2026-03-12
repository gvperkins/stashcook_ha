
from __future__ import annotations
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_REFRESH_TOKEN, CONF_UPDATE_INTERVAL,
    SENSOR_TODAY_TITLE, SENSOR_TODAY_IMAGE, SENSOR_TODAY_URL, SENSOR_TODAY_NOTES,
    SENSOR_TOMORROW_TITLE, SENSOR_TOMORROW_IMAGE, SENSOR_TOMORROW_URL, SENSOR_TOMORROW_NOTES,
    SENSOR_WEEK_COUNT,
)
from .coordinator import StashcookCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    update_minutes = entry.data.get(CONF_UPDATE_INTERVAL)

    coordinator = StashcookCoordinator(hass, refresh_token, update_minutes)
    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = [
        StashcookTodayTitleSensor(coordinator),
        StashcookTodayImageSensor(coordinator),
        StashcookTodayUrlSensor(coordinator),
        StashcookTodayNotesSensor(coordinator),
        StashcookTomorrowTitleSensor(coordinator),
        StashcookTomorrowImageSensor(coordinator),
        StashcookTomorrowUrlSensor(coordinator),
        StashcookTomorrowNotesSensor(coordinator),
        StashcookWeekCountSensor(coordinator),
    ]
    async_add_entities(entities)


def _extract_first(meals: list[dict[str, Any]]) -> dict[str, Any] | None:
    return meals[0] if meals else None


def _title(meal: dict[str, Any] | None) -> str:
    return (meal.get("name") or meal.get("title") or "Meal planned") if meal else "Nothing Planned Today"


def _image(meal: dict[str, Any] | None) -> str:
    return (meal.get("image") or meal.get("imageUrl") or meal.get("thumbnail") or "") if meal else ""


def _url(meal: dict[str, Any] | None) -> str:
    return (meal.get("url") or meal.get("recipeUrl") or "") if meal else ""


def _notes(meal: dict[str, Any] | None) -> str:
    return (meal.get("notes") or "") if meal else ""


class _BaseStashcookSensor(CoordinatorEntity[StashcookCoordinator], SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: StashcookCoordinator, name: str, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id

class StashcookTodayTitleSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Today's Meal Title", SENSOR_TODAY_TITLE)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("today", []))
        return _title(meal)

class StashcookTodayImageSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Today's Meal Image", SENSOR_TODAY_IMAGE)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("today", []))
        return _image(meal)

class StashcookTodayUrlSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Today's Meal URL", SENSOR_TODAY_URL)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("today", []))
        return _url(meal)

class StashcookTodayNotesSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Today's Meal Notes", SENSOR_TODAY_NOTES)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("today", []))
        return _notes(meal)

class StashcookTomorrowTitleSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Tomorrow's Meal Title", SENSOR_TOMORROW_TITLE)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("tomorrow", []))
        return _title(meal)

class StashcookTomorrowImageSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Tomorrow's Meal Image", SENSOR_TOMORROW_IMAGE)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("tomorrow", []))
        return _image(meal)

class StashcookTomorrowUrlSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Tomorrow's Meal URL", SENSOR_TOMORROW_URL)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("tomorrow", []))
        return _url(meal)

class StashcookTomorrowNotesSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Tomorrow's Meal Notes", SENSOR_TOMORROW_NOTES)

    @property
    def native_value(self) -> str:
        meal = _extract_first(self.coordinator.data.get("tomorrow", []))
        return _notes(meal)

class StashcookWeekCountSensor(_BaseStashcookSensor):
    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "Meals This Week Count", SENSOR_WEEK_COUNT)

    @property
    def native_value(self) -> int:
        week = self.coordinator.data.get("week", [])
        return len(week) if isinstance(week, list) else 0

    @property
    def extra_state_attributes(self) -> dict:
        return {"meals": self.coordinator.data.get("week", [])}
