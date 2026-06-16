"""Runtime readiness and environment wiring tests."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from app.config import InsecureAdminAuthConfigError, Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRET_ENV_NAMES = {"BOT_INTERNAL_TOKEN", "JWT_SECRET", "INITIAL_ADMIN_PASSWORD"}
CRITICAL_DEPLOYMENT_ENV_NAMES = {
    "APP_ENV",
    "DATABASE_URL",
    "JWT_SECRET",
    "INITIAL_ADMIN_PASSWORD",
    "BOT_INTERNAL_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "OPENAI_API_KEY",
    "OPENAI_IMAGE_MODEL",
    "OPENAI_IMAGE_SIZE",
    "OPENAI_IMAGE_QUALITY",
    "OPENAI_IMAGE_OUTPUT_FORMAT",
    "OPENAI_IMAGE_TIMEOUT_SECONDS",
    "USER_PHOTO_MASK_MODE",
    "USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT",
    "BOT_BACKEND_TIMEOUT_SECONDS",
    "BOT_GENERATION_TIMEOUT_SECONDS",
    "UPLOAD_DIR",
    "MAX_UPLOAD_BYTES",
    "RATE_LIMIT_WINDOW_SECONDS",
    "ADMIN_LOGIN_RATE_LIMIT",
    "BOT_API_RATE_LIMIT",
    "GENERATION_RATE_LIMIT",
    "UPLOAD_RATE_LIMIT",
    "VITE_API_BASE_URL",
    "VITE_BACKEND_PUBLIC_URL",
}


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for raw_line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _value = line.split("=", 1)
        keys.add(key)
    return keys


def test_env_example_covers_docker_compose_references() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    compose_vars = set(re.findall(r"\$\{([A-Z0-9_]+)(?::-[^}]*)?\}", compose_text))

    assert compose_vars - _env_example_keys() == set()


def test_readme_documents_critical_deployment_environment() -> None:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    missing = {name for name in CRITICAL_DEPLOYMENT_ENV_NAMES if name not in readme_text}

    assert missing == set()


def test_readme_documents_release_checklist_invariants() -> None:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()

    required_phrases = {
        "required production environment",
        "deployment checklist",
        "post-merge smoke checks",
        "bot_internal_token",
        "одинаковый strong token",
        "placeholder запрещен",
        "github actions jobs green",
        "x-request-id",
        "retry-after",
        "rollback",
    }

    assert {phrase for phrase in required_phrases if phrase not in readme_text} == set()


def test_frontend_vite_env_does_not_expose_backend_secrets() -> None:
    vite_keys = {key for key in _env_example_keys() if key.startswith("VITE_")}
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "admin-frontend" / "src").rglob("*")
        if path.is_file()
    )

    assert vite_keys == {"VITE_API_BASE_URL", "VITE_BACKEND_PUBLIC_URL"}
    for secret_name in SECRET_ENV_NAMES:
        assert secret_name not in frontend_text


def test_upload_bytes_overrides_upload_size_megabytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "10")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "64")
    get_settings.cache_clear()

    try:
        assert get_settings().max_upload_size_bytes == 64
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("app_env", "jwt_secret", "initial_admin_password", "bot_internal_token"),
    [
        ("production", "", "strong-password", "strong-bot-token"),
        ("prod", "change_me", "strong-password", "strong-bot-token"),
        ("staging", "strong-secret", "", "strong-bot-token"),
        ("production", "strong-secret", "admin12345", "strong-bot-token"),
        ("production", "strong-secret", "strong-password", ""),
        ("production", "strong-secret", "strong-password", "change_me_bot_internal_token"),
    ],
)
def test_production_runtime_rejects_placeholder_admin_secrets(
    app_env: str,
    jwt_secret: str,
    initial_admin_password: str,
    bot_internal_token: str,
) -> None:
    settings = Settings(
        app_env=app_env,
        jwt_secret=jwt_secret,
        initial_admin_password=initial_admin_password,
        bot_internal_token=bot_internal_token,
    )

    with pytest.raises(InsecureAdminAuthConfigError):
        settings.validate_admin_auth_config()


def test_development_runtime_accepts_demo_defaults() -> None:
    settings = Settings(app_env="development", jwt_secret="change_me", initial_admin_password="admin12345")

    settings.validate_admin_auth_config()


def test_bot_config_reads_internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_INTERNAL_TOKEN", "runtime-test-token")
    monkeypatch.setenv("BOT_BACKEND_TIMEOUT_SECONDS", "11")
    monkeypatch.setenv("BOT_GENERATION_TIMEOUT_SECONDS", "181")
    module_path = REPO_ROOT / "bot" / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("runtime_bot_config", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert module.get_settings().bot_internal_token == "runtime-test-token"
    assert module.get_settings().backend_request_timeout_seconds == 11
    assert module.get_settings().generation_request_timeout_seconds == 181
