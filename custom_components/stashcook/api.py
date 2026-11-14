"""Small async client for the Stashcook web API."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import dt as dt_util

from .const import API_BASE, API_VERSION, ORIGIN, RECIPE_EXPAND, REFERER

_LOGGER = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class StashcookAuthError(Exception):
    """The refresh token was rejected."""


class StashcookApiError(Exception):
    """Any other API failure."""


class StashcookClient:
    """Refresh-token based client. Cookies are sent explicitly, never via a shared jar."""

    def __init__(
        self,
        hass: HomeAssistant,
        refresh_token: str,
        on_token_rotated: Callable[[str], None] | None = None,
    ) -> None:
        self.refresh_token = refresh_token
        self._on_token_rotated = on_token_rotated
        self._session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
        self._access_token: str | None = None
        self._expiry_ts: float = 0

    def _headers(self, cookie: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "api-version": API_VERSION,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "User-Agent": UA,
            "Cookie": cookie,
        }

    async def async_refresh_access_token(self) -> str:
        headers = self._headers(f"refreshToken={self.refresh_token}")
        async with self._session.put(f"{API_BASE}/session", headers=headers, data=b"") as resp:
            if resp.status in (400, 401, 403):
                raise StashcookAuthError(f"Refresh rejected ({resp.status})")
            if resp.status != 200:
                raise StashcookApiError(f"Refresh failed ({resp.status})")
            data = await resp.json(content_type=None)
            rotated = resp.cookies.get("refreshToken")
        if rotated and rotated.value and rotated.value != self.refresh_token:
            _LOGGER.debug("Stashcook rotated the refresh token")
            self.refresh_token = rotated.value
            if self._on_token_rotated:
                self._on_token_rotated(rotated.value)

        access = data.get("accessToken")
        if not access:
            raise StashcookApiError("No accessToken in refresh response")
        expiry = dt_util.parse_datetime(data.get("expiry") or "")
        self._expiry_ts = expiry.timestamp() if expiry else dt_util.utcnow().timestamp() + 3600
        self._access_token = access
        return access

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        for attempt in (1, 2):
            if not self._access_token or self._expiry_ts - 60 < dt_util.utcnow().timestamp():
                await self.async_refresh_access_token()
            headers = self._headers(
                f"refreshToken={self.refresh_token}; accessToken={self._access_token}"
            )
            async with self._session.get(f"{API_BASE}{path}", headers=headers, params=params) as resp:
                if resp.status == 401 and attempt == 1:
                    self._access_token = None
                    continue
                if resp.status != 200:
                    raise StashcookApiError(f"GET {path} failed ({resp.status})")
                return await resp.json(content_type=None)
        raise StashcookApiError(f"GET {path} unauthorised")

    async def async_get_meals(self, start: str, end: str) -> list[dict[str, Any]]:
        data = await self._get("/meals", {"start": start, "end": end})
        return data if isinstance(data, list) else []

    async def async_get_recipe(self, recipe_id: str) -> dict[str, Any]:
        return await self._get(f"/recipes/{recipe_id}", {"expand": RECIPE_EXPAND})
