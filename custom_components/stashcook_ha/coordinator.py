
from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, List, Tuple
from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    API_BASE, API_VERSION, ORIGIN, REFERER,
    CONF_REFRESH_TOKEN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL,
)

class StashcookClient:
    def __init__(self, hass: HomeAssistant, refresh_token: str) -> None:
        self.hass = hass
        self.refresh_token = refresh_token
        self._access_token: str | None = None
        self._expiry_ts: float | None = None

    async def _session(self) -> ClientSession:
        return self.hass.helpers.aiohttp_client.async_get_clientsession()

    async def _attach_cookie(self, session: ClientSession, name: str, value: str) -> None:
        # Ensure cookies are set for api.stashcook.com so aiohttp sends them
        session.cookie_jar.update_cookies({name: value}, response_url="https://api.stashcook.com/")

    async def async_refresh_access_token(self) -> Tuple[str, float]:
        session = await self._session()
        headers = {
            "Accept": "application/json",
            "api-version": API_VERSION,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "User-Agent": "HomeAssistant-Stashcook",
        }
        await self._attach_cookie(session, "refreshToken", self.refresh_token)
        async with session.put(f"{API_BASE}/session", headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Refresh failed: {resp.status} {text}")
            data = await resp.json()
        access = data.get("accessToken")
        expiry_iso = data.get("expiry")
        if not access or not expiry_iso:
            raise Exception("Unexpected refresh response")
        try:
            expiry_dt = dt_util.parse_datetime(expiry_iso)
            if expiry_dt is None:
                raise ValueError("parse failed")
            expiry_ts = expiry_dt.timestamp()
        except Exception:
            expiry_ts = dt_util.utcnow().timestamp() + 6*24*3600
        self._access_token = access
        self._expiry_ts = expiry_ts
        return access, expiry_ts

    async def _ensure_access(self) -> str:
        now_ts = dt_util.utcnow().timestamp()
        if self._access_token and self._expiry_ts and (self._expiry_ts - 60) > now_ts:
            return self._access_token
        access, _ = await self.async_refresh_access_token()
        return access

    async def async_get_meals(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        access = await self._ensure_access()
        session = await self._session()
        headers = {
            "Accept": "application/json",
            "api-version": API_VERSION,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "User-Agent": "HomeAssistant-Stashcook",
        }
        await self._attach_cookie(session, "refreshToken", self.refresh_token)
        await self._attach_cookie(session, "accessToken", access)
        params = {"start": start_date, "end": end_date}
        async with session.get(f"{API_BASE}/meals", headers=headers, params=params) as resp:
            if resp.status == 401:
                await self.async_refresh_access_token()
                await self._attach_cookie(session, "refreshToken", self.refresh_token)
                await self._attach_cookie(session, "accessToken", self._access_token or "")
                async with session.get(f"{API_BASE}/meals", headers=headers, params=params) as resp2:
                    if resp2.status != 200:
                        raise Exception(f"Meals fetch failed: {resp2.status} {await resp2.text()}")
                    return await resp2.json()
            if resp.status != 200:
                raise Exception(f"Meals fetch failed: {resp.status} {await resp.text()}")
            return await resp.json()

class StashcookCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, refresh_token: str, update_minutes: int | None = None) -> None:
        self.client = StashcookClient(hass, refresh_token)
        interval = timedelta(minutes=update_minutes or DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            hass.helpers.logger.getLogger(DOMAIN),
            name="Stashcook Coordinator",
            update_interval=interval,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        from datetime import timedelta as td
        try:
            now = dt_util.now()
            today = now.date()
            tomorrow = (now + td(days=1)).date()
            monday_delta = today.weekday()
            monday = today - td(days=monday_delta)
            sunday = monday + td(days=6)

            today_str = today.isoformat()
            tomorrow_str = tomorrow.isoformat()
            week_start = monday.isoformat()
            week_end = sunday.isoformat()

            today_items = await self.client.async_get_meals(today_str, today_str)
            tomorrow_items = await self.client.async_get_meals(tomorrow_str, tomorrow_str)
            week_items = await self.client.async_get_meals(week_start, week_end)

            return {
                "today": today_items,
                "tomorrow": tomorrow_items,
                "week": week_items,
            }
        except Exception as err:
            raise UpdateFailed(str(err)) from err
