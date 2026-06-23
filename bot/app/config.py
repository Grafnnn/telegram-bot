"""Bot configuration."""

import os
from dataclasses import dataclass

TOKEN_PLACEHOLDER = "put_token_here"
BOT_INTERNAL_TOKEN_PLACEHOLDER = "change_me_bot_internal_token"


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BotSettings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", TOKEN_PLACEHOLDER)
    backend_api_url: str = os.getenv("BOT_BACKEND_API_URL", "http://backend:8000/api")
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    bot_internal_token: str = os.getenv("BOT_INTERNAL_TOKEN", BOT_INTERNAL_TOKEN_PLACEHOLDER)
    backend_request_timeout_seconds: float = _get_float("BOT_BACKEND_TIMEOUT_SECONDS", 10)
    generation_request_timeout_seconds: float = _get_float("BOT_GENERATION_TIMEOUT_SECONDS", 180)
    user_photo_try_on_enabled: bool = False
    user_photo_garment_crop_try_on_enabled: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_bot_token != TOKEN_PLACEHOLDER)


def get_settings() -> BotSettings:
    return BotSettings(
        user_photo_try_on_enabled=_get_bool("BOT_USER_PHOTO_TRY_ON_ENABLED", False),
        # Keep the crop-only experiment out of the user-facing bot. It returns a standalone garment image,
        # not an edit of the user's original photo, so an existing env value must not re-enable it.
        user_photo_garment_crop_try_on_enabled=False,
    )