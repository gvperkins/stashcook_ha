# Stashcook — Home Assistant Custom Integration

**Version:** 0.1.2  
**Updated:** 2026-03-12

This integration pulls your meal plan from **Stashcook** and exposes sensors in **Home Assistant**. It supports automatic token refresh using your **refreshToken** (no manual cookie updates). When no meal is planned for today, the title sensor reports **"Nothing Planned Today"**.

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
4. Paste your `refreshToken` (encoded, exactly as in the cookie).
5. Choose an update interval (default: 60 minutes).

## HACS Install (Custom Repository)
1. In HACS → Integrations → **Custom repositories**, add `https://github.com/gvperkins/stashcook_ha` with category **Integration**.
2. Install **Stashcook** and restart Home Assistant.
3. Add the integration from Devices & Services.

## Lovelace Example
```yaml
type: picture-entity
entity: sensor.stashcook_meal_today_title
image: "{ states('sensor.stashcook_meal_today_image') }"
name: "{ states('sensor.stashcook_meal_today_title') }"
show_state: true
```

## How it Works
- The integration calls `PUT https://api.stashcook.com/session` with your `refreshToken` **cookie** to get an `accessToken` and expiry.
- Then it calls `GET https://api.stashcook.com/meals?start=YYYY-MM-DD&end=YYYY-MM-DD` with both cookies.
- If a request returns `401`, it refreshes the access token and retries once.

## Troubleshooting
- **Invalid token** during setup: Ensure the token is the **encoded** cookie value (contains `%2F`, `%3D%3D`).
- **No meal today**: Title sensor shows *Nothing Planned Today* when empty.
- **Image not showing**: Use the image sensor value in your card.
- **HACS version issues**: Create a GitHub **release tag** (e.g., `v0.1.2`).
