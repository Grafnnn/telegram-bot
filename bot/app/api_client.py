"""Backend API client for the bot."""

import asyncio
import logging
from typing import Any

import aiohttp

from app.config import get_settings

logger = logging.getLogger(__name__)


class BackendAPIClient:
    def __init__(self, base_url: str, bot_internal_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.bot_internal_token = (
            bot_internal_token if bot_internal_token is not None else get_settings().bot_internal_token
        )

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        if self.bot_internal_token:
            headers = {**headers, "X-Bot-Token": self.bot_internal_token}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.request(method, url, headers=headers, **kwargs) as response:
                    if response.status >= 400:
                        text = await response.text()
                        logger.error("Backend error %s %s: %s", response.status, url, text)
                        return None
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.error("Backend is unavailable: %s", exc)
            return None

    async def upsert_user(self, telegram_id: int, username: str | None = None, first_name: str | None = None, last_name: str | None = None) -> dict | None:
        return await self._request(
            "POST",
            "/bot/users/upsert",
            json={"telegram_id": telegram_id, "username": username, "first_name": first_name, "last_name": last_name},
        )

    async def get_fabrics(self, page: int = 1, limit: int = 10) -> list[dict]:
        data = await self._request("GET", "/catalog/fabrics", params={"page": page, "limit": limit})
        return (data or {}).get("items", [])

    async def get_garment_styles(self) -> list[dict]:
        data = await self._request("GET", "/catalog/garment-styles")
        return (data or {}).get("items", [])

    async def recommend_fabrics(self, user_text: str) -> list[dict]:
        data = await self._request("POST", "/catalog/fabrics/recommend", json={"user_text": user_text, "limit": 5})
        if isinstance(data, dict):
            return data.get("items", [])
        return data or []

    async def select_fabric(self, telegram_id: int, fabric_id: str) -> dict | None:
        return await self._request("POST", f"/bot/users/{telegram_id}/selected-fabric", json={"fabric_id": fabric_id})

    async def get_selected_fabric(self, telegram_id: int) -> dict | None:
        return await self._request("GET", f"/bot/users/{telegram_id}/selected-fabric")

    async def select_garment_style(self, telegram_id: int, garment_style_id: str) -> dict | None:
        return await self._request("POST", f"/bot/users/{telegram_id}/selected-garment-style", json={"garment_style_id": garment_style_id})

    async def get_selected_garment_style(self, telegram_id: int) -> dict | None:
        return await self._request("GET", f"/bot/users/{telegram_id}/selected-garment-style")

    async def get_selection(self, telegram_id: int) -> dict | None:
        return await self._request("GET", f"/bot/users/{telegram_id}/selection")

    async def create_catalog_style_generation(self, telegram_id: int) -> dict | None:
        return await self._request("POST", "/generations/catalog-style", json={"telegram_id": telegram_id})
