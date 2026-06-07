"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

OPENAI_API_KEY_PLACEHOLDER = "put_openai_key_here"
TELEGRAM_BOT_TOKEN_PLACEHOLDER = "put_token_here"
BOT_INTERNAL_TOKEN_PLACEHOLDER = "change_me_bot_internal_token"
JWT_SECRET_PLACEHOLDER = "change_me"
INITIAL_ADMIN_PASSWORD_PLACEHOLDER = "admin12345"
PRODUCTION_LIKE_ENVS = {"production", "prod", "staging"}


class MissingOpenAIKeyError(RuntimeError):
    """Raised when an AI feature is called without a configured OpenAI key."""


class InsecureAdminAuthConfigError(RuntimeError):
    """Raised when admin auth settings are unsafe for production-like runtime."""


class InsecureBootstrapConfigError(RuntimeError):
    """Raised when database bootstrap settings are unsafe for the runtime."""


def _read_env_file(path: Path = Path(".env")) -> dict[str, str]:
    """Read simple KEY=VALUE entries from an environment file if it exists."""

    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get_value(name: str, default: str, env_file: dict[str, str]) -> str:
    """Return an environment value with process variables taking precedence."""

    return os.getenv(name, env_file.get(name, default))


def _get_int(name: str, default: int, env_file: dict[str, str]) -> int:
    """Return an integer environment value."""

    return int(_get_value(name, str(default), env_file))


def _get_bool(name: str, default: bool, env_file: dict[str, str]) -> bool:
    """Return a boolean environment value."""

    value = _get_value(name, str(default).lower(), env_file).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _get_optional_int(name: str, default: int | None, env_file: dict[str, str]) -> int | None:
    """Return an optional integer environment value."""

    value = _get_value(name, "" if default is None else str(default), env_file).strip()
    return int(value) if value else None


@dataclass(frozen=True)
class Settings:
    """Runtime settings sourced from `.env` or process environment."""

    app_env: str = "development"

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/fashion_bot"
    postgres_db: str = "fashion_bot"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_public_url: str = "http://localhost:8000"

    admin_frontend_url: str = "http://localhost:5173"

    jwt_secret: str = JWT_SECRET_PLACEHOLDER
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    telegram_bot_token: str = TELEGRAM_BOT_TOKEN_PLACEHOLDER
    bot_backend_api_url: str = "http://backend:8000/api"
    bot_internal_token: str = BOT_INTERNAL_TOKEN_PLACEHOLDER

    openai_api_key: str = OPENAI_API_KEY_PLACEHOLDER

    upload_dir: Path = Path("/app/uploads")
    max_upload_size_mb: int = 10
    max_upload_bytes: int | None = None

    initial_admin_email: str = "admin@example.com"
    initial_admin_password: str = INITIAL_ADMIN_PASSWORD_PLACEHOLDER

    seed_demo_data: bool = False

    @classmethod
    def from_env(cls, env_file_path: Path = Path(".env")) -> "Settings":
        """Build settings from `.env` and process environment variables."""

        env_file = _read_env_file(env_file_path)
        values: dict[str, Any] = {
            "app_env": _get_value("APP_ENV", cls.app_env, env_file),
            "database_url": _get_value("DATABASE_URL", cls.database_url, env_file),
            "postgres_db": _get_value("POSTGRES_DB", cls.postgres_db, env_file),
            "postgres_user": _get_value("POSTGRES_USER", cls.postgres_user, env_file),
            "postgres_password": _get_value("POSTGRES_PASSWORD", cls.postgres_password, env_file),
            "backend_host": _get_value("BACKEND_HOST", cls.backend_host, env_file),
            "backend_port": _get_int("BACKEND_PORT", cls.backend_port, env_file),
            "backend_public_url": _get_value("BACKEND_PUBLIC_URL", cls.backend_public_url, env_file),
            "admin_frontend_url": _get_value("ADMIN_FRONTEND_URL", cls.admin_frontend_url, env_file),
            "jwt_secret": _get_value("JWT_SECRET", cls.jwt_secret, env_file),
            "jwt_algorithm": _get_value("JWT_ALGORITHM", cls.jwt_algorithm, env_file),
            "access_token_expire_minutes": _get_int(
                "ACCESS_TOKEN_EXPIRE_MINUTES", cls.access_token_expire_minutes, env_file
            ),
            "telegram_bot_token": _get_value("TELEGRAM_BOT_TOKEN", cls.telegram_bot_token, env_file),
            "bot_backend_api_url": _get_value("BOT_BACKEND_API_URL", cls.bot_backend_api_url, env_file),
            "bot_internal_token": _get_value("BOT_INTERNAL_TOKEN", cls.bot_internal_token, env_file),
            "openai_api_key": _get_value("OPENAI_API_KEY", cls.openai_api_key, env_file),
            "upload_dir": Path(_get_value("UPLOAD_DIR", str(cls.upload_dir), env_file)),
            "max_upload_size_mb": _get_int("MAX_UPLOAD_SIZE_MB", cls.max_upload_size_mb, env_file),
            "max_upload_bytes": _get_optional_int("MAX_UPLOAD_BYTES", cls.max_upload_bytes, env_file),
            "initial_admin_email": _get_value("INITIAL_ADMIN_EMAIL", cls.initial_admin_email, env_file),
            "initial_admin_password": _get_value("INITIAL_ADMIN_PASSWORD", cls.initial_admin_password, env_file),
            "seed_demo_data": _get_bool("SEED_DEMO_DATA", cls.seed_demo_data, env_file),
        }
        return cls(**values)

    @property
    def max_upload_size_bytes(self) -> int:
        """Configured maximum upload size in bytes."""

        if self.max_upload_bytes is not None and self.max_upload_bytes > 0:
            return self.max_upload_bytes
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_openai_configured(self) -> bool:
        """Return whether AI features can call OpenAI."""

        return bool(self.openai_api_key and self.openai_api_key != OPENAI_API_KEY_PLACEHOLDER)

    @property
    def is_telegram_bot_configured(self) -> bool:
        """Return whether the Telegram bot token was replaced with a real value."""

        return bool(self.telegram_bot_token and self.telegram_bot_token != TELEGRAM_BOT_TOKEN_PLACEHOLDER)

    @property
    def is_bot_internal_token_configured(self) -> bool:
        """Return whether bot-to-backend API access has a real shared token."""

        return bool(self.bot_internal_token and self.bot_internal_token != BOT_INTERNAL_TOKEN_PLACEHOLDER)

    @property
    def is_production_like(self) -> bool:
        """Return whether runtime should reject development placeholders."""

        return self.app_env.strip().lower() in PRODUCTION_LIKE_ENVS

    def validate_admin_auth_config(self) -> None:
        """Reject insecure admin auth settings for production-like runtime."""

        if not self.is_production_like:
            return
        if not self.jwt_secret or self.jwt_secret == JWT_SECRET_PLACEHOLDER:
            raise InsecureAdminAuthConfigError("JWT_SECRET must be set for production-like admin auth.")
        if not self.initial_admin_password or self.initial_admin_password == INITIAL_ADMIN_PASSWORD_PLACEHOLDER:
            raise InsecureAdminAuthConfigError(
                "INITIAL_ADMIN_PASSWORD must be set for production-like admin auth."
            )
        if not self.is_bot_internal_token_configured:
            raise InsecureAdminAuthConfigError(
                "BOT_INTERNAL_TOKEN must be set for production-like bot API access."
            )

    def validate_bootstrap_config(self) -> None:
        """Reject unsafe database bootstrap settings before creating seed records."""

        self.validate_admin_auth_config()
        if self.is_production_like and self.seed_demo_data:
            raise InsecureBootstrapConfigError(
                "SEED_DEMO_DATA must be disabled for production-like database bootstrap."
            )

    def require_openai_api_key(self) -> str:
        """Return the OpenAI key or raise a clear AI-feature error."""

        if not self.is_openai_configured:
            raise MissingOpenAIKeyError(
                "OPENAI_API_KEY is not configured. Copy .env.example to .env, "
                "replace put_openai_key_here with a real key, and restart the backend."
            )
        return self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings.from_env()
