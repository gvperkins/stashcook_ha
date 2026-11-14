"""Sensors for the Stashcook meal planner."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StashcookCoordinator

MEAL_ATTRS = frozenset({
    "key", "date", "slot", "title", "source", "planned", "recipe_id", "url", "image",
    "image_large", "prep_minutes", "cook_minutes", "total_minutes", "servings", "source_name",
    "source_url", "headline", "badge", "note", "intro", "ingredients", "method", "extras",
    "split", "has_calendar",
})
SLOT_SENSORS = [
    ("today", 0, "dinner"), ("today", 0, "lunch"), ("today", 0, "lunch_prep"),
    ("today", 0, "breakfast"), ("tomorrow", 1, "dinner"), ("tomorrow", 1, "lunch"),
    ("tomorrow", 1, "lunch_prep"), ("tomorrow", 1, "breakfast"),
]
SLOT_ICONS = {
    "dinner": "mdi:silverware-fork-knife",
    "lunch": "mdi:food",
    "lunch_prep": "mdi:pot-steam",
    "breakfast": "mdi:coffee",
}


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: StashcookCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [MealSensor(coordinator, *s) for s in SLOT_SENSORS]
    entities += [WeekSensor(coordinator), PrepSensor(coordinator)]
    async_add_entities(entities)


class _Base(CoordinatorEntity[StashcookCoordinator], SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator: StashcookCoordinator, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self.entity_id = f"sensor.stashcook_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="Stashcook",
            manufacturer="Stashcook",
            entry_type=DeviceEntryType.SERVICE,
        )


class MealSensor(_Base):
    """Today's or tomorrow's meal for one slot. The state is the title."""

    _unrecorded_attributes = MEAL_ATTRS

    def __init__(self, coordinator: StashcookCoordinator, when: str, offset: int, slot: str) -> None:
        super().__init__(
            coordinator, f"{when}_{slot}", f"Stashcook {when} {slot.replace('_', ' ')}", SLOT_ICONS[slot]
        )
        self._offset = offset
        self._slot = slot

    def _meal(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        if not data.get("today"):
            return None
        target = (date.fromisoformat(data["today"]) + timedelta(days=self._offset)).isoformat()
        for day in data.get("days", []):
            if day["date"] == target:
                return day["meals"].get(self._slot)
        return None

    @property
    def native_value(self) -> str:
        meal = self._meal()
        return meal["title"][:255] if meal else "Nothing planned"

    @property
    def entity_picture(self) -> str | None:
        meal = self._meal()
        return meal.get("image") if meal else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._meal() or {}


class WeekSensor(_Base):
    """Last week, this week and next week (21 days from last Monday), with full meal
    detail and each day's prep lines.

    The state is the number of planner meals Monday to Sunday of this week.
    """

    _unrecorded_attributes = frozenset({"days", "start", "today", "monday"})

    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "week", "Stashcook week", "mdi:calendar-week")

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or {}
        monday = data.get("monday")
        if not monday:
            return 0
        sunday = (date.fromisoformat(monday) + timedelta(days=6)).isoformat()
        return sum(
            1
            for d in data.get("days", [])
            if monday <= d["date"] <= sunday
            for m in d["meals"].values()
            if m.get("planned")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "today": data.get("today"),
            "start": data.get("start"),
            "monday": data.get("monday"),
            "days": data.get("days", []),
        }


class PrepSensor(_Base):
    """Prep banner lines: "Tonight:" notes, night-before jobs and Sunday lunch prep."""

    _unrecorded_attributes = frozenset({"lines"})

    def __init__(self, coordinator: StashcookCoordinator) -> None:
        super().__init__(coordinator, "prep_reminders", "Stashcook prep reminders", "mdi:alarm")

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("prep", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"lines": (self.coordinator.data or {}).get("prep", [])}
