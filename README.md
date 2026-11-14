# Stashcook for Home Assistant

**Version:** 0.2.1

Pulls your **Stashcook** meal plan into Home Assistant: today's and tomorrow's meals by slot, full recipe detail (image, times, servings, ingredients, method, source) and a two-week list for dashboards. Optionally merges the matching meal-plan calendar event ("Family Dinner - X", "Lunch - X", "Lunch Prep - X") so meals without a Stashcook recipe still get ingredients, method and reminders.

Requires Home Assistant 2025.1 or newer.

## Install

### HACS (custom repository)
1. HACS → Integrations → ⋮ → **Custom repositories** → add `https://github.com/gvperkins/stashcook_ha` (category **Integration**).
2. Install **Stashcook** and restart Home Assistant.

### Manual
Copy `custom_components/stashcook` into `/config/custom_components/` and restart.

## Set up
1. In app.stashcook.com open DevTools → **Application** → **Cookies** and copy the `refreshToken` value. (A HAR export will not contain it; browsers strip cookies from HARs.)
2. **Settings → Devices & Services → Add Integration → Stashcook**, paste the token.
3. Optionally pick the meal-plan calendar (default `calendar.family`) and the update interval (default 30 minutes).

The token is stored in the config entry, never in YAML. If Stashcook rotates it, the integration saves the new one. If it is rejected, HA asks you to re-authenticate.

## Sensors

| Entity | State | Attributes |
|---|---|---|
| `sensor.stashcook_today_dinner`, `_today_lunch`, `_today_lunch_prep`, `_today_breakfast` | Meal title or `Nothing planned` | Full meal (see below); `entity_picture` is the Stashcook image |
| `sensor.stashcook_tomorrow_dinner`, `_tomorrow_lunch`, `_tomorrow_lunch_prep`, `_tomorrow_breakfast` | as above | as above |
| `sensor.stashcook_week` | Planner meals Mon–Sun this week | `today`, `monday` (this week), `start` (last Monday), `days`: 21 days (last, this and next week) of `{date, weekday, meals: {slot: meal}, prep: [lines]}` |
| `sensor.stashcook_prep_reminders` | Number of lines | `lines`: "Tonight:" notes from today's events, "the night before" jobs from tomorrow's, and "Lunch prep today" on prep days |

Meal attributes: `key`, `date`, `slot`, `title`, `source` (`stashcook` / `calendar`), `planned`, `recipe_id`, `url`, `image`, `image_large`, `prep_minutes`, `cook_minutes`, `total_minutes`, `servings`, `source_name`, `source_url`, `headline` (first bold line of the event), `badge` (Quick / Make ahead / Roast / Leftovers), `note`, `intro`, `ingredients` (`[{text, header}]`), `method` (list of steps), `extras` (`[{label, text}]`, e.g. Tonight, Reheat), `split` (per-person lunches on office days), `has_calendar`.

Large attributes are excluded from the recorder.

Where both exist, the calendar's ingredients and method win (they describe what was actually bought); the Stashcook recipe fills any gaps and supplies the image, times and source.

## Upgrading from 0.1.x
- The old `stashcook_meal_today_*`, `stashcook_meal_tomorrow_*` and `stashcook_meals_week_count` sensors are replaced by the sensors above.
- The duplicate `custom_components/stashcook_ha` folder is gone; only `custom_components/stashcook` is installed.
- 0.1.x does not load on recent Home Assistant (it used the removed `hass.helpers`), so there is normally nothing to migrate.

## Development
Parser tests need only Python: `python tests/test_parser.py`.
