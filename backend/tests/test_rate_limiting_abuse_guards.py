"""Rate limiting and abuse guard tests."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.rate_limit import rate_limiter
from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage
from app.models.telegram_user import TelegramUser

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}


def _png_bytes(size: tuple[int, int] = (1, 1), color: tuple[int, int, int] = (20, 120, 180)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_1X1 = _png_bytes()
SENSITIVE_STRINGS = {
    "test_bot_internal_token",
    "admin12345",
    "authorization",
    "x-bot-token",
    "password",
    "traceback",
}


@pytest.fixture(autouse=True)
def isolated_limiter_state():
    rate_limiter.clear()
    get_settings.cache_clear()
    yield
    rate_limiter.clear()
    get_settings.cache_clear()


def _set_rate_limits(monkeypatch: pytest.MonkeyPatch, **limits: int) -> None:
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    for name, value in limits.items():
        monkeypatch.setenv(name, str(value))
    get_settings.cache_clear()
    rate_limiter.clear()


def _assert_safe_429(response) -> None:
    assert response.status_code == 429, response.text
    assert response.headers.get("retry-after")
    body = response.text.lower()
    for value in SENSITIVE_STRINGS:
        assert value not in body


def _create_telegram_user() -> int:
    telegram_id = 820_000_000 + uuid4().int % 1_000_000
    with SessionLocal() as db:
        db.add(TelegramUser(telegram_id=telegram_id))
        db.commit()
    return telegram_id


def _create_fabric() -> str:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"RL-{uuid4().hex[:10]}",
            name="Rate limited fabric",
            category="cotton",
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Test fabric for rate limiting.",
            status="published",
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        image_url = f"/uploads/fabrics/{uuid4().hex}.png"
        path = get_settings().upload_dir / image_url.removeprefix("/uploads/")
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (300, 300), color=(80, 140, 210)).save(path, format="PNG")
        db.add(FabricImage(fabric_id=fabric.id, image_url=image_url, image_type="texture", sort_order=1))
        db.commit()
        return str(fabric.id)


def _post_user_photo(client: TestClient, fabric_id: str):
    return client.post(
        "/api/generations/user-photo",
        headers=BOT_HEADERS,
        data={"fabric_id": fabric_id},
        files={"photo": ("photo.png", PNG_1X1, "image/png")},
    )


def test_admin_login_rate_limit_allows_first_request_then_429(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_rate_limits(monkeypatch, ADMIN_LOGIN_RATE_LIMIT=1)

    first = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    assert first.status_code == 200, first.text

    second = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    _assert_safe_429(second)


def test_disabled_admin_login_rate_limit_keeps_dev_path_usable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_rate_limits(monkeypatch, ADMIN_LOGIN_RATE_LIMIT=0)

    first = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    second = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text


def test_bot_facing_api_rate_limit_returns_429_after_threshold(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_rate_limits(monkeypatch, BOT_API_RATE_LIMIT=1)
    telegram_id = 830_000_000 + uuid4().int % 1_000_000
    payload = {"telegram_id": telegram_id}

    first = client.post("/api/bot/users/upsert", headers=BOT_HEADERS, json=payload)
    assert first.status_code == 200, first.text

    second = client.post("/api/bot/users/upsert", headers=BOT_HEADERS, json=payload)
    _assert_safe_429(second)


def test_catalog_style_generation_rate_limit_returns_429_after_threshold(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_rate_limits(monkeypatch, GENERATION_RATE_LIMIT=1)
    telegram_id = _create_telegram_user()
    payload = {"telegram_id": telegram_id}

    first = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json=payload)
    assert first.status_code == 400, first.text

    second = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json=payload)
    _assert_safe_429(second)


def test_user_photo_upload_rate_limit_allows_first_valid_upload_then_429(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_rate_limits(monkeypatch, GENERATION_RATE_LIMIT=10, UPLOAD_RATE_LIMIT=1)
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "off")
    monkeypatch.setenv("USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT", "false")
    get_settings.cache_clear()
    fabric_id = _create_fabric()

    first = _post_user_photo(client, fabric_id)
    assert first.status_code == 201, first.text

    second = _post_user_photo(client, fabric_id)
    _assert_safe_429(second)
