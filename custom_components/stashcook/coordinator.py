"""Data coordinator: Stashcook planner + recipe detail, merged with the meal-plan calendar."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parser
from .api import StashcookApiError, StashcookAuthError, StashcookClient
from .const import (
    APP_RECIPE_URL,
    CONF_CALENDAR,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DAYS_AHEAD,
    DEFAULT_CALENDAR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    RECIPE_CACHE_HOURS,
    SLOTS,
    TAG_SLOTS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


def _opt(entry: ConfigEntry, key: str, default: Any) -> Any:
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


class StashcookCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the planner for Monday of this week + 13 days."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.client = StashcookClient(hass, entry.data[CONF_REFRESH_TOKEN], self._token_rotated)
        self.calendar_entity: str = _opt(entry, CONF_CALENDAR, DEFAULT_CALENDAR) or ""
        self._recipes: dict[str, tuple[datetime, dict[str, Any]]] = {}
        minutes = int(_opt(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=minutes),
        )

    def _token_rotated(self, token: str) -> None:
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_REFRESH_TOKEN: token}
        )

    async def _recipe(self, recipe_id: str) -> dict[str, Any] | None:
        now = dt_util.utcnow()
        cached = self._recipes.get(recipe_id)
        if cached and now - cached[0] < timedelta(hours=RECIPE_CACHE_HOURS):
            return cached[1]
        try:
            data = await self.client.async_get_recipe(recipe_id)
        except StashcookApiError as err:
            _LOGGER.warning("Could not fetch Stashcook recipe %s: %s", recipe_id, err)
            return cached[1] if cached else None
        self._recipes[recipe_id] = (now, data)
        return data

    async def _calendar_events(self, start: date, end: date) -> list[dict[str, Any]]:
        if not self.calendar_entity or self.hass.states.get(self.calendar_entity) is None:
            return []
        try:
            resp = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "start_date_time": f"{start.isoformat()} 00:00:00",
                    "end_date_time": f"{end.isoformat()} 00:00:00",
                },
                target={"entity_id": self.calendar_entity},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - the calendar is optional enrichment
            _LOGGER.warning("Could not read %s: %s", self.calendar_entity, err)
            return []
        return (resp or {}).get(self.calendar_entity, {}).get("events", [])

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().date()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=DAYS_AHEAD - 1)
        try:
            meals = await self.client.async_get_meals(start.isoformat(), end.isoformat())
        except StashcookAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        events = await self._calendar_events(start, end + timedelta(days=1))
        cal: dict[tuple[str, str], dict[str, Any]] = {}
        for ev in events:
            found = parser.slot_for_title(ev.get("summary", ""))
            if not found:
                continue
            slot, title = found
            day = str(ev.get("start", ""))[:10]
            cal.setdefault((day, slot), {"title": title, "description": ev.get("description") or ""})

        planner: dict[tuple[str, str], dict[str, Any]] = {}
        for meal in sorted(meals, key=lambda m: (m.get("date", ""), m.get("order", 0))):
            slot = next((TAG_SLOTS[t] for t in meal.get("tags", []) if t in TAG_SLOTS), None)
            if slot is None:
                slot = "dinner" if meal.get("order", 0) == 0 else "lunch"
            planner.setdefault((meal.get("date", "")[:10], slot), meal)

        days: list[dict[str, Any]] = []
        for offset in range(DAYS_AHEAD):
            day = start + timedelta(days=offset)
            iso = day.isoformat()
            slots: dict[str, Any] = {}
            for slot in SLOTS:
                meal = await self._build_meal(iso, slot, planner.get((iso, slot)), cal.get((iso, slot)))
                if meal:
                    slots[slot] = meal
            days.append({"date": iso, "weekday": day.strftime("%a"), "meals": slots})

        return {
            "today": today.isoformat(),
            "start": start.isoformat(),
            "days": days,
            "prep": self._prep_lines(days, today),
        }

    async def _build_meal(
        self,
        iso: str,
        slot: str,
        planned: dict[str, Any] | None,
        event: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not planned and not event:
            return None
        parsed = parser.parse_description(event["description"] if event else None)
        recipe_id = (planned or {}).get("recipeId")
        recipe = await self._recipe(recipe_id) if recipe_id else None

        title = (
            (recipe or {}).get("name")
            or (planned or {}).get("noteText")
            or (event or {}).get("title")
            or "Meal planned"
        )
        # Diane's calendar text wins (it reflects what was actually bought);
        # the Stashcook recipe fills any gaps.
        ingredients = parsed["ingredients"]
        method = parsed["method"]
        intro = parsed["intro"]
        if not method and not ingredients and intro:
            method, intro = parser.split_steps(" ".join(intro)), []
        if recipe:
            if not ingredients:
                ingredients = [
                    {"text": i.get("text", ""), "header": False}
                    for i in recipe.get("ingredients") or []
                    if i.get("text")
                ]
            if not method:
                method = [m.get("text", "") for m in recipe.get("method") or [] if m.get("text")]

        images = (recipe or {}).get("images") or []
        image = images[0] if images else {}
        source = (recipe or {}).get("source") or {}
        headline = parsed["headline"]
        badge = parser.badge_for(headline, title)
        note = headline
        if headline and badge and " - " in headline and headline.lower().startswith(badge.lower()):
            note = headline.split(" - ", 1)[1]

        return {
            "key": f"{iso}|{slot}",
            "date": iso,
            "slot": slot,
            "title": title,
            "source": "stashcook" if recipe else "calendar",
            "planned": planned is not None,
            "recipe_id": recipe_id,
            "url": APP_RECIPE_URL.format(id=recipe_id) if recipe_id else None,
            "image": image.get("medium") or image.get("large"),
            "image_large": image.get("large") or image.get("medium"),
            "prep_minutes": (recipe or {}).get("prepTimeMinutes"),
            "cook_minutes": (recipe or {}).get("cookTimeMinutes"),
            "total_minutes": (recipe or {}).get("totalTimeMinutes") or parser.minutes_from(headline),
            "servings": (recipe or {}).get("servings"),
            "source_name": source.get("name"),
            "source_url": source.get("url"),
            "headline": headline,
            "badge": badge,
            "note": note,
            "intro": intro,
            "ingredients": ingredients,
            "method": method,
            "extras": parsed["extras"],
            "split": parser.lunch_split(title, parsed["extras"]) if slot == "lunch" else None,
            "has_calendar": event is not None,
        }

    @staticmethod
    def _prep_lines(days: list[dict[str, Any]], today: date) -> list[str]:
        by_date = {d["date"]: d["meals"] for d in days}
        todays = by_date.get(today.isoformat(), {})
        tomorrows = by_date.get((today + timedelta(days=1)).isoformat(), {})
        lines: list[str] = []
        prep = todays.get("lunch_prep")
        if prep:
            extra = f" ({prep['headline']})" if prep.get("headline") else ""
            lines.append(f"Lunch prep today: {prep['title']}{extra}")
        for meal in todays.values():
            lines += parser.prep_lines_for({"extras": meal.get("extras", [])}, tomorrow=False)
        for meal in tomorrows.values():
            lines += parser.prep_lines_for({"extras": meal.get("extras", [])}, tomorrow=True)
        out: list[str] = []
        for line in lines:
            if line not in out:
                out.append(line)
        return out
