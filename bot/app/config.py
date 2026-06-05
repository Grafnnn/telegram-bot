"""Bot configuration."""

import os
from dataclasses import dataclass

TOKEN_PLACEHOLDER = "put_token_here"
BOT_INTERNAL_TOKEN_PLACEHOLDER = "change_me_bot_internal_token"


@dataclass(frozen=True)
class BotSettings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", TOKEN_PLACEHOLDER)
    backend_api_url: str = os.getenv("BOT_BACKEND_API_URL", "http://backend:8000/api")
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    bot_internal_token: str = os.getenv("BOT_INTERNAL_TOKEN", BOT_INTERNAL_TOKEN_PLACEHOLDER)

    @property
    def is_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_bot_token != TOKEN_PLACEHOLDER)


def get_settings() -> BotSettings:
    return BotSettings()
