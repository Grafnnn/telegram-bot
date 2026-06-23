"""Catalog-style image generation API tests."""

from __future__ import annotations

from io import BytesIO
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage
from app.models.garment_style import GarmentStyle
from app.models.generation import Generation
from app.models.telegram_user import TelegramUser
from app.schemas.generation import GenerationRead

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}
WRONG_BOT_HEADERS = {"X-Bot-Token": "wrong"}


def _png_bytes(size: tuple[int, int] = (1, 1), color: tuple[int, int, int] = (20, 120, 180)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_1X1 = _png_bytes()


def _write_upload(relative_url: str) -> None:
    path = get_settings().upload_dir / relative_url.removeprefix("/uploads/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def _create_user(selected_fabric_id=None, selected_garment_style_id=None) -> int:
    telegram_id = 600_000_000 + uuid4().int % 1_000_000
    with SessionLocal() as db:
        user = TelegramUser(
            telegram_id=telegram_id,
            selected_fabric_id=selected_fabric_id,
            selected_garment_style_id=selected_garment_style_id,
        )
        db.add(user)
        db.commit()
    return telegram_id


def _create_fabric(with_texture: bool = True, status: str = "published"):
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"GEN-{uuid4().hex[:10]}",
            name="Generation fabric",
            category="cotton",
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Реальная опубликованная ткань для визуализации.",
            status=status,
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        if with_texture:
            image_url = f"/uploads/fabrics/{uuid4().hex}.png"
            _write_upload(image_url)
            db.add(FabricImage(fabric_id=fabric.id, image_url=image_url, image_type="texture", sort_order=1))
            db.commit()
        return fabric.id


def _create_style(with_base: bool = True, with_mask: bool = False, status: str = "published"):
    with SessionLocal() as db:
        base_url = f"/uploads/garment-styles/{uuid4().hex}.png" if with_base else None
        mask_url = f"/uploads/garment-styles/{uuid4().hex}.png" if with_mask else None
        if base_url:
            _write_upload(base_url)
        if mask_url:
            _write_upload(mask_url)
        style = GarmentStyle(
            name="Generation style",
            category="dress",
            description="Реальный опубликованный фасон для визуализации.",
            status=status,
            base_image_url=base_url,
            mask_image_url=mask_url,
        )
        db.add(style)
        db.commit()
        db.refresh(style)
        return style.id


def test_catalog_style_generation_requires_internal_token(client: TestClient) -> None:
    telegram_id = _create_user()
    response = client.post("/api/generations/catalog-style", json={"telegram_id": telegram_id})
    assert response.status_code == 401, response.text


def test_catalog_style_generation_rejects_invalid_internal_token(client: TestClient) -> None:
    telegram_id = _create_user()
    response = client.post(
        "/api/generations/catalog-style",
        headers=WRONG_BOT_HEADERS,
        json={"telegram_id": telegram_id},
    )
    assert response.status_code == 401, response.text


def test_catalog_style_generation_requires_selected_fabric(client: TestClient) -> None:
    telegram_id = _create_user()
    response = client.post(
        "/api/generations/catalog-style",
        headers=BOT_HEADERS,
        json={"telegram_id": telegram_id},
    )
    assert response.status_code == 400, response.text
    assert "ткань" in response.json()["detail"].lower()


def test_catalog_style_generation_requires_selected_style(client: TestClient) -> None:
    fabric_id = _create_fabric()
    telegram_id = _create_user(selected_fabric_id=fabric_id)
    response = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json={"telegram_id": telegram_id})
    assert response.status_code == 400, response.text
    assert "фасон" in response.json()["detail"].lower()


def test_catalog_style_generation_requires_texture_image(client: TestClient) -> None:
    fabric_id = _create_fabric(with_texture=False)
    style_id = _create_style()
    telegram_id = _create_user(selected_fabric_id=fabric_id, selected_garment_style_id=style_id)
    response = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json={"telegram_id": telegram_id})
    assert response.status_code == 400, response.text
    assert "texture image" in response.json()["detail"]


def test_catalog_style_generation_requires_style_base_image(client: TestClient) -> None:
    fabric_id = _create_fabric()
    style_id = _create_style(with_base=False)
    telegram_id = _create_user(selected_fabric_id=fabric_id, selected_garment_style_id=style_id)
    response = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json={"telegram_id": telegram_id})
    assert response.status_code == 400, response.text
    assert "base image" in response.json()["detail"]


def test_catalog_style_generation_without_openai_key_creates_failed_generation(client: TestClient) -> None:
    fabric_id = _create_fabric()
    style_id = _create_style(with_mask=True)
    telegram_id = _create_user(selected_fabric_id=fabric_id, selected_garment_style_id=style_id)
    response = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json={"telegram_id": telegram_id})
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert "OpenAI API key" in payload["error_message"]
    assert payload["mode"] == "catalog_style"
    assert payload["fabric_id"] == str(fabric_id)
    assert payload["garment_style_id"] == str(style_id)


def test_catalog_style_generation_provider_error_is_normalized(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    style_id = _create_style(with_mask=True)
    telegram_id = _create_user(selected_fabric_id=fabric_id, selected_garment_style_id=style_id)
    log_messages: list[str] = []

    def fake_generate(
        base_image_path: str,
        fabric_texture_path: str,
        mask_image_path: str | None,
        prompt: str,
    ) -> bytes:
        raise RuntimeError(
            "provider traceback Authorization: Bearer provider-token password=hunter2 data:image/png;base64,"
            + "A" * 120
        )

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_catalog_style", fake_generate)
    monkeypatch.setattr(
        generation_routes.logger,
        "warning",
        lambda message, *args: log_messages.append(message % args),
    )
    response = client.post(
        "/api/generations/catalog-style",
        headers=BOT_HEADERS,
        json={"telegram_id": telegram_id},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_message"] == generation_routes.IMAGE_ERROR
    assert "traceback" not in payload["error_message"].lower()
    log_text = "\n".join(log_messages)
    assert "RuntimeError" in log_text
    assert "provider-token" not in log_text
    assert "hunter2" not in log_text
    assert "data:image/png;base64" not in log_text


def test_catalog_style_generation_saves_mocked_result(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    style_id = _create_style(with_mask=True)
    telegram_id = _create_user(selected_fabric_id=fabric_id, selected_garment_style_id=style_id)

    def fake_generate(base_image_path: str, fabric_texture_path: str, mask_image_path: str | None, prompt: str) -> bytes:
        assert base_image_path
        assert fabric_texture_path
        assert mask_image_path
        with Image.open(mask_image_path) as provider_mask:
            assert provider_mask.mode == "RGBA"
            assert provider_mask.getchannel("A").getextrema()[0] == 0
        assert "Replace only the fabric" in prompt
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_catalog_style", fake_generate)
    response = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json={"telegram_id": telegram_id})
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result_image_url"].startswith("/uploads/generations/")
    assert (get_settings().upload_dir / payload["result_image_url"].removeprefix("/uploads/")).exists()
    with SessionLocal() as db:
        generation = db.get(Generation, payload["id"])
        assert generation is not None
        assert generation.result_image_url == payload["result_image_url"]


def test_catalog_style_generation_reuses_active_request(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    style_id = _create_style(with_mask=True)
    telegram_id = _create_user(selected_fabric_id=fabric_id, selected_garment_style_id=style_id)
    with SessionLocal() as db:
        user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
        assert user is not None
        generation = Generation(
            telegram_user_id=user.id,
            fabric_id=fabric_id,
            garment_style_id=style_id,
            mode="catalog_style",
            status="pending",
        )
        db.add(generation)
        db.commit()
        db.refresh(generation)
        generation_id = str(generation.id)

    def fail_generate(*_args, **_kwargs) -> bytes:
        raise AssertionError("provider should not be called for an active generation")

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_catalog_style", fail_generate)

    response = client.post("/api/generations/catalog-style", headers=BOT_HEADERS, json={"telegram_id": telegram_id})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == generation_id
    assert payload["status"] == "pending"


def test_get_generation_missing_id_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/generations/{uuid4()}")

    assert response.status_code == 404, response.text


def test_generation_schema_rejects_unknown_status() -> None:
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        GenerationRead.model_validate(
            {
                "id": uuid4(),
                "mode": "catalog_style",
                "status": "failed Authorization: Bearer provider-token",
                "created_at": now,
                "updated_at": now,
            }
        )
