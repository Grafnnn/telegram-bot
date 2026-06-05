"""User-photo generation upload validation tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}
WRONG_BOT_HEADERS = {"X-Bot-Token": "wrong"}

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xde\xa6\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _create_fabric() -> str:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"PHOTO-{uuid4().hex[:10]}",
            name="User photo fabric",
            category="cotton",
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Тестовая ткань для user-photo generation.",
            status="published",
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        return str(fabric.id)


def _post_user_photo(
    client: TestClient,
    fabric_id: str,
    content: bytes,
    content_type: str,
    headers: dict[str, str] | None = None,
):
    return client.post(
        "/api/generations/user-photo",
        headers=headers,
        data={"fabric_id": fabric_id},
        files={"photo": ("photo.png", content, content_type)},
    )


def test_user_photo_generation_accepts_valid_image_with_internal_token(client: TestClient) -> None:
    fabric_id = _create_fabric()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["mode"] == "user_photo"
    assert payload["fabric_id"] == fabric_id
    assert payload["user_photo_url"].startswith("/uploads/user-photos/")


def test_user_photo_generation_requires_internal_token(client: TestClient) -> None:
    response = _post_user_photo(client, str(uuid4()), PNG_1X1, "image/png")

    assert response.status_code == 401, response.text


def test_user_photo_generation_rejects_invalid_internal_token(client: TestClient) -> None:
    response = _post_user_photo(client, str(uuid4()), PNG_1X1, "image/png", WRONG_BOT_HEADERS)

    assert response.status_code == 401, response.text


def test_user_photo_generation_rejects_unsupported_mime(client: TestClient) -> None:
    fabric_id = _create_fabric()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "text/plain", BOT_HEADERS)

    assert response.status_code == 415, response.text


def test_user_photo_generation_rejects_oversized_upload(client: TestClient, monkeypatch) -> None:
    fabric_id = _create_fabric()
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4")
    get_settings.cache_clear()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 413, response.text


def test_user_photo_generation_rejects_empty_upload(client: TestClient) -> None:
    fabric_id = _create_fabric()

    response = _post_user_photo(client, fabric_id, b"", "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text


def test_user_photo_generation_rejects_invalid_image_content(client: TestClient) -> None:
    fabric_id = _create_fabric()

    response = _post_user_photo(client, fabric_id, b"not an image", "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text
