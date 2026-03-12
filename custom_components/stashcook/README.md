# Stashcook — Home Assistant Custom Integration

**Version:** 0.1.0  
**Updated:** 2026-03-12

This integration pulls your meal plan from **Stashcook** and exposes sensors in **Home Assistant**. It supports automatic token refresh using your **refreshToken** (no manual cookie updates). When no meal is planned for today, sensors report **"Nothing Planned Today"**.

## Features
- UI setup (Config Flow) — paste your `refreshToken` once
- Auto refresh via `PUT /session`
- Fetches **today**, **tomorrow**, and **current week (Mon–Sun)**
- Sensors (verbose names):
  - `sensor.stashcook_meal_today_title`
  - `sensor.stashcook_meal_today_image`
  - `sensor.stashcook_meal_today_url`
  - `sensor.stashcook_meal_today_notes`
  - `sensor.stashcook_meal_tomorrow_title`
  - `sensor.stashcook_meal_tomorrow_image`
  - `sensor.stashcook_meal_tomorrow_url`
  - `sensor.stashcook_meal_tomorrow_notes`
  - `sensor.stashcook_meals_week_count` (attributes include the raw weekly list)

## Install (Manual)
1. Copy the `custom_components/stashcook` folder into your HA `/config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Stashcook**.
4. Paste your `refreshToken` (from your browser cookie for `https://api.stashcook.com`).
5. Choose an update interval (default: 60 minutes).

## Install via HACS (Custom Repository)
Until this repository is public, use manual install above. If hosted on GitHub:
1. HACS → Integrations → **Custom repositories** → Add your repo URL, category **Integration**.
2. Search **Stashcook** in HACS, install, and restart HA.
3. Add integration via UI as above.

## Lovelace Examples
**Picture Entity** (title and image):
```yaml
type: picture-entity
entity: sensor.stashcook_meal_today_title
image: "{{ state_attr('sensor.stashcook_meal_today_image','friendly_name') or state_attr('sensor.stashcook_meal_today_title','image') }}"
name: "{{ states('sensor.stashcook_meal_today_title') }}"
```

**Markdown card**:
```yaml
type: markdown
title: Today's Meal
content: |
  **{{ states('sensor.stashcook_meal_today_title') }}**
  {% set img = states('sensor.stashcook_meal_today_image') %}
  {% if img %}
  ![Meal Image]({{ img }})
  {% endif %}
```

## How it Works
- The integration calls `PUT https://api.stashcook.com/session` with your `refreshToken` cookie to obtain an `accessToken` and expiry.
- Then it calls `GET https://api.stashcook.com/meals?start=YYYY-MM-DD&end=YYYY-MM-DD` with both cookies.
- If a request returns `401`, it refreshes the access token and retries once.

## Privacy & Security
- Your refresh token is stored encrypted inside HA's config entry storage.
- Treat your refresh token like a password. If exposed, log out and back into Stashcook to rotate it.

## Troubleshooting
- **Invalid token** during setup: Re‑copy the `refreshToken` from your browser cookies (Application → Cookies → `https://api.stashcook.com`).
- **Empty today**: The "today" sensors will show **Nothing Planned Today** when your planner has no entries.
- **Image not showing**: Ensure your card references the *image URL sensor* value.
- **Frequent 401s**: Your token may be revoked. Grab a fresh `refreshToken` and reconfigure the integration.
