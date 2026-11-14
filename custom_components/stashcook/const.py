"""Constants for the Stashcook integration."""
DOMAIN = "stashcook"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_CALENDAR = "calendar_entity"

DEFAULT_UPDATE_INTERVAL = 30  # minutes
DEFAULT_CALENDAR = "calendar.family"
RECIPE_CACHE_HOURS = 12
DAYS_AHEAD = 14  # Monday of this week + 13 days, so the weekend can show next week

API_BASE = "https://api.stashcook.com"
API_VERSION = "2025.01.06"
ORIGIN = "https://app.stashcook.com"
REFERER = "https://app.stashcook.com/"
APP_RECIPE_URL = "https://app.stashcook.com/recipe/{id}"
RECIPE_EXPAND = "Ingredients,Method,Notes"

TAG_DINNER = "27778bbb-9c13-4d9c-81c3-ad7053d35209"
TAG_LUNCH = "1ecea98f-5f42-43e8-b824-fa6f0bf33a09"
TAG_BREAKFAST = "24520f28-37fa-4cb0-b207-1a0eb01e2506"
TAG_SLOTS = {TAG_DINNER: "dinner", TAG_LUNCH: "lunch", TAG_BREAKFAST: "breakfast"}

SLOTS = ("breakfast", "lunch_prep", "lunch", "dinner")
