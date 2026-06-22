from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage
from app.models.telegram_user import TelegramUser
from app.services.mask_service import STRICT_MASK_REQUIRED_MESSAGE

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}


def _png_bytes(size: tuple[int, int] = (300, 300), color: tuple[int, int, int] = (20, 120, 180)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _write_upload(relative_url: str) -> None:
    path = get_settings().upload_dir / relative_url.removeprefix("/uploads/")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (300, 300), color=(40, 120, 190)).save(path, format="PNG")


def _create_fabric() -> str:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"PROD-GATE-{uuid4().hex[:10]}",
            name="Production gate fabric",
            category="cotton",
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Тестовая ткань для production-like generated-mask gate.",
            status="published",
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        image_url = f"/uploads/fabrics/{uuid4().hex}-texture.png"
        _write_upload(image_url)
        db.add(FabricImage(fabric_id=fabric.id, image_url=image_url, image_type="texture", sort_order=1))
        db.commit()
        return str(fabric.id)


def _create_telegram_user() -> int:
    telegram_id = 710_000_000 + uuid4().int % 1_000_000
    with SessionLocal() as db:
        db.add(TelegramUser(telegram_id=telegram_id, username="prod_gate_photo_user"))
        db.commit()
    return telegram_id


def test_telegram_generated_mask_is_blocked_in_staging_before_provider(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "off")
    monkeypatch.setenv("USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT", "true")
    get_settings.cache_clear()

    fabric_id = _create_fabric()
    telegram_id = _create_telegram_user()
    provider_called = False

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return _png_bytes()

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = client.post(
            "/api/generations/user-photo",
            headers=BOT_HEADERS,
            data={"fabric_id": fabric_id, "telegram_id": str(telegram_id)},
            files={"photo": ("photo.png", _png_bytes(), "image/png")},
        )
    finally:
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("USER_PHOTO_MASK_MODE", raising=False)
        monkeypatch.delenv("USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == STRICT_MASK_REQUIRED_MESSAGE
    assert provider_called is False
