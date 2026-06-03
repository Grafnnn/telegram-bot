from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class ApiResult:
    ok: bool
    data: Any = None
    error: str | None = None
    status_code: int | None = None


class BackendApiClient:
    def __init__(self, base_url: str, *, timeout: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs: Any) -> ApiResult:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.request(method, path, **kwargs)
                if response.status_code >= 400:
                    return ApiResult(
                        ok=False,
                        status_code=response.status_code,
                        error=self._extract_error(response),
                    )
                return ApiResult(ok=True, data=response.json(), status_code=response.status_code)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
            return ApiResult(ok=False, error="Backend is unavailable")
        except httpx.HTTPError:
            return ApiResult(ok=False, error="Backend request failed")
        except ValueError:
            return ApiResult(ok=False, error="Backend returned invalid response")

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Backend request failed"
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, str):
            return detail
        return "Backend request failed"

    async def upsert_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> ApiResult:
        return await self._request(
            "POST",
            "/api/bot/users/upsert",
            json={
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

    async def get_fabrics(self) -> ApiResult:
        return await self._request("GET", "/api/catalog/fabrics")

    async def recommend_fabrics(self, user_text: str) -> ApiResult:
        return await self._request(
            "POST",
            "/api/catalog/fabrics/recommend",
            json={"user_text": user_text, "limit": 5},
        )

    async def select_fabric(self, telegram_id: int, fabric_id: str) -> ApiResult:
        return await self._request(
            "POST",
            f"/api/bot/users/{telegram_id}/selected-fabric",
            json={"fabric_id": fabric_id},
        )

    async def get_selected_fabric(self, telegram_id: int) -> ApiResult:
        return await self._request("GET", f"/api/bot/users/{telegram_id}/selected-fabric")
