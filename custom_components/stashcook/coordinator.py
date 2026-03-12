
from __future__ import annotations
import logging
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

_LOGGER = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
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
        session.cookie_jar.update_cookies({name: value}, response_url="https://api.stashcook.com/")
        _LOGGER.debug("Attached cookie %s len=%s", name, len(value) if value else 0)

    async def async_refresh_access_token(self) -> Tuple[str, float]:
        session = await self._session()
        headers = {
            "Accept": "application/json",
            "api-version": API_VERSION,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "User-Agent": UA,
            # Also include cookie inline as belt-and-braces
            "Cookie": f"refreshToken={self.refresh_token}",
        }

        await self._attach_cookie(session, "refreshToken", self.refresh_token)
        _LOGGER.debug("PUT %s/session to refresh token", API_BASE)
        async with session.put(f"{API_BASE}/session", headers=headers, data=b"") as resp:
            text = await resp.text()
            _LOGGER.debug("Refresh status=%s body=%s", resp.status, text if len(text) < 512 else text[:512] + "...")
            if resp.status != 200:
                raise Exception(f"Refresh failed: {resp.status} {text}")
            data = await resp.json()

        access = data.get("accessToken")
        expiry_iso = data.get("expiry")
        if not access or not expiry_iso:
            raise Exception(f"Unexpected refresh response: {data}")
        try:
            expiry_dt = dt_util.parse_datetime(expiry_iso)
            if expiry_dt is None:
                raise ValueError("parse_datetime None")
            expiry_ts = expiry_dt.timestamp()
        except Exception:
            expiry_ts = dt_util.utcnow().timestamp() + 6*24*3600
        self._access_token = access
        self._expiry_ts = expiry_ts
        _LOGGER.debug("Refreshed access token len=%s expTs=%s", len(access), int(expiry_ts))
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
            "User-Agent": UA,
            "Cookie": f"refreshToken={self.refresh_token}; accessToken={access}",
        }
        await self._attach_cookie(session, "refreshToken", self.refresh_token)
        await self._attach_cookie(session, "accessToken", access)

        params = {"start": start_date, "end": end_date}
        _LOGGER.debug("GET %s/meals %s", API_BASE, params)
        async with session.get(f"{API_BASE}/meals", headers=headers, params=params) as resp:
            text = await resp.text()
            if resp.status == 401:
                _LOGGER.debug("401 meals; retry after refresh")
                await self.async_refresh_access_token()
                await self._attach_cookie(session, "refreshToken", self.refresh_token)
                await self._attach_cookie(session, "accessToken", self._access_token or "")
                headers["Cookie"] = f"refreshToken={self.refresh_token}; accessToken={self._access_token or ''}"
                async with session.get(f"{API_BASE}/meals", headers=headers, params=params) as resp2:
                    text2 = await resp2.text()
                    if resp2.status != 200:
                        raise Exception(f"Meals fetch failed: {resp2.status} {text2}")
                    return await resp2.json()
            if resp.status != 200:
                raise Exception(f"Meals fetch failed: {resp.status} {text}")
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
        try:
            from datetime import timedelta as td
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

            return {"today": today_items, "tomorrow": tomorrow_items, "week": week_items}
        except Exception as err:
            raise UpdateFailed(str(err)) from err
