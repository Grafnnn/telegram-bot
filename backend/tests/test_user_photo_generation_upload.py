"""User-photo generation upload validation tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage
from app.models.generation import Generation
from app.models.telegram_user import TelegramUser

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}
WRONG_BOT_HEADERS = {"X-Bot-Token": "wrong"}

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xde\xa6\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _write_upload(relative_url: str) -> None:
    path = get_settings().upload_dir / relative_url.removeprefix("/uploads/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def _create_fabric(with_texture: bool = True, status: str = "published") -> str:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"PHOTO-{uuid4().hex[:10]}",
            name="User photo fabric",
            category="cotton",
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Тестовая ткань для user-photo generation.",
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
        return str(fabric.id)


def _create_telegram_user() -> int:
    telegram_id = 700_000_000 + uuid4().int % 1_000_000
    with SessionLocal() as db:
        db.add(TelegramUser(telegram_id=telegram_id, username="photo_user"))
        db.commit()
    return telegram_id


def _post_user_photo(
    client: TestClient,
    fabric_id: str,
    content: bytes,
    content_type: str,
    headers: dict[str, str] | None = None,
    telegram_id: int | None = None,
):
    data = {"fabric_id": fabric_id}
    if telegram_id is not None:
        data["telegram_id"] = str(telegram_id)
    return client.post(
        "/api/generations/user-photo",
        headers=headers,
        data=data,
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
    assert payload["status"] == "failed"
    assert "OpenAI API key" in payload["error_message"]


def test_user_photo_generation_requires_texture_image(client: TestClient) -> None:
    fabric_id = _create_fabric(with_texture=False)
    telegram_id = _create_telegram_user()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS, telegram_id=telegram_id)

    assert response.status_code == 400, response.text
    assert "texture image" in response.json()["detail"]
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    admin_payload = admin_response.json()
    assert admin_payload["total"] == 1
    [admin_generation] = admin_payload["items"]
    assert admin_generation["mode"] == "user_photo"
    assert admin_generation["status"] == "failed"
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["fabric"]["name"] == "User photo fabric"
    assert admin_generation["telegram_user"]["telegram_id"] == telegram_id
    assert "texture image" in admin_generation["error_message"]


def test_user_photo_generation_unpublished_fabric_persists_failed_record(client: TestClient) -> None:
    fabric_id = _create_fabric(status="draft")
    telegram_id = _create_telegram_user()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS,  telegram_id=telegram_id)

    assert response.status_code == 400, response.text
    assert "оопубликован" in response.json()["detail"]
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    admin_payload = admin_response.json()
    assert admin_payload["total"] == 1
    [admin_generation] = admin_payload["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["telegram_user"]["telegram_id"] == telegram_id
    assert "опубликован" in admin_generation["error_message"]


def test_user_photo_generation_missing_fabric_does_not_create_record(client: TestClient) -> None:
    telegram_id = _create_telegram_user()

    response = _post_user_photo(client, str(uuid4()), PNG_1X1, "image/png", BOT_HEADERS, telegram_id=telegram_id)

    assert response.status_code == 404, response.text
    with SessionLocal() as db:
        assert db.scalar(select(Generation)) is None


def test_user_photo_generation_saves_mocked_result(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()

    def fake_generate(user_photo_path: str, fabric_texture_path: str, prompt: str) -> bytes:
        assert user_photo_path
        assert fabric_texture_path
        assert "visible garment" in prompt
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result_image_url"].startswith("/uploads/generations/")
    assert (get_settings().upload_dir / payload["result_image_url"].removeprefix("/uploads/")).exists()

    admin_response = client.get("/api/admin/generations?status=completed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    admin_payload = admin_response.json()
    assert admin_payload["total"] == 1
    [admin_generation] = admin_payload["items"]
    assert admin_generation["id"] == payload["id"]
    assert admin_generation["mode"] == "user_photo"
    assert admin_generation["status"] == "completed"
    assert admin_generation["user_photo_url"].startswith("/uploads/user-photos/")
    assert admin_generation["result_image_url"] == payload["result_image_url"]
    assert admin_generation["fabric"]["sku"].startswith("PHOTO-")
    assert admin_generation["fabric"]["name"] == "User photo fabric"
    assert admin_generation["fabric"]["category"] == "cotton"


def test_user_photo_generation_provider_error_is_normalized(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    log_messages: list[str] = []

    def fake_generate(user_photo_path: str, fabric_texture_path: str, prompt: str) -> bytes:
        raise RuntimeError(
            "provider traceback Authorization: Bearer provider-token password=hunter2 data:image/png;base64,"
            + "A" * 120
        )

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(
        generation_routes.logger,
        "warning",
        lambda message, *args: log_messages.append(message % args),
    )

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_message"] == generation_routes.IMAGE_ERROR
    assert "traceback" not in payload["error_message"].lower()
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["id"] == payload["id"]
    assert admin_generation["status"] == "failed"
    assert admin_generation["error_message"] == generation_routes.IMAGE_ERROR
    assert admin_generation["fabric"]["name"] == "User photo fabric"
    log_text = "\n".join(log_messages)
    assert "RuntimeError" in log_text
    assert "provider-token" not in log_text
    assert "hunter2" not in log_text
    assert "data:image/png;base64" not in log_text


def test_user_photo_generation_requires_internal_token(client: TestClient) -> None:
    response = _post_user_photo(client, str(uuid4()), PNG_1X1, "image/png")

    assert response.status_code == 401, response.text
    with SessionLocal() as db:
        assert db.scalar(select(Generation)) is None


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
    telegram_id = _create_telegram_user()

    response = _post_user_photo(client, fabric_id, b"not an image", "image/png", BOT_HEADERS, telegram_id=telegram_id)

    assert response.status_code == 400, response.text
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["telegram_user"]["telegram_id"] == telegram_id
    assert admin_generation["user_photo_url"] is None
    assert "корректное изображение" in admin_generation["error_message"]
