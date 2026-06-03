"""Backend API client for the bot."""

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class BackendAPIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.request(method, url, **kwargs) as response:
                    if response.status >= 400:
                        text = await response.text()
                        logger.error("Backend error %s %s: %s", response.status, url, text)
                        return None
                    return await response.json()
        except aiohttp.ClientError as exc:
            logger.error("Backend is unavailable: %s", exc)
            return None

    async def get_fabrics(self) -> list[dict]:
        data = await self._request("GET", "/catalog/fabrics")
        return (data or {}).get("items", [])

    async def get_garment_styles(self) -> list[dict]:
        data = await self._request("GET", "/catalog/garment-styles")
        return (data or {}).get("items", [])

    async def recommend_fabrics(self, user_text: str) -> list[dict]:
        data = await self._request("POST", "/catalog/fabrics/recommend", json={"user_text": user_text, "limit": 5})
        return data or []
