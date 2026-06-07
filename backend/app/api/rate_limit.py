"""FastAPI dependencies for scoped in-memory rate limiting."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings
from app.utils.rate_limiter import InMemoryRateLimiter

RATE_LIMIT_MESSAGE = "Слишком много запросов. Повторите позже."
rate_limiter = InMemoryRateLimiter()


def _client_host(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "unknown"


def _safe_key_part(value: object) -> str:
    text = str(value or "unknown").strip().lower()
    return text[:128] if text else "unknown"


def _key(*parts: object) -> str:
    return "|".join(_safe_key_part(part).replace("|", "_") for part in parts)


async def _json_field(request: Request, field: str) -> str:
    try:
        payload = await request.json()
    except Exception:
        return "unknown"
    if not isinstance(payload, dict):
        return "unknown"
    return _safe_key_part(payload.get(field))


def _check_rate_limit(key: str, limit: int, settings: Settings) -> None:
    decision = rate_limiter.hit(key, limit, settings.rate_limit_window_seconds)
    if decision.allowed:
        return
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        RATE_LIMIT_MESSAGE,
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


async def rate_limit_admin_login(request: Request) -> None:
    settings = get_settings()
    email = await _json_field(request, "email")
    _check_rate_limit(
        _key("admin-login", _client_host(request), email),
        settings.admin_login_rate_limit,
        settings,
    )


async def rate_limit_bot_api(request: Request) -> None:
    settings = get_settings()
    _check_rate_limit(
        _key("bot-api", request.url.path, _client_host(request)),
        settings.bot_api_rate_limit,
        settings,
    )


async def rate_limit_catalog_style_generation(request: Request) -> None:
    settings = get_settings()
    telegram_id = await _json_field(request, "telegram_id")
    _check_rate_limit(
        _key("generation", request.url.path, telegram_id),
        settings.generation_rate_limit,
        settings,
    )


async def rate_limit_user_photo_generation(request: Request) -> None:
    settings = get_settings()
    host_key = _key(request.url.path, _client_host(request))
    _check_rate_limit(_key("generation", host_key), settings.generation_rate_limit, settings)
    _check_rate_limit(_key("upload", host_key), settings.upload_rate_limit, settings)


async def rate_limit_upload(request: Request) -> None:
    settings = get_settings()
    _check_rate_limit(
        _key("upload", request.url.path, _client_host(request)),
        settings.upload_rate_limit,
        settings,
    )
