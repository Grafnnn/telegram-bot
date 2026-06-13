"""User-photo generation upload validation tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}
WRONG_BOT_HEADERS = {"X-Bot-Token": "wrong"}

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xde\xa6\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


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
    assert payload["status"] == "failed"
    assert "OpenAI API key" in payload["error_message"]


def test_user_photo_generation_requires_texture_image(client: TestClient) -> None:
    fabric_id = _create_fabric(with_texture=False)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text
    assert "texture image" in response.json()["detail"]


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
    log_text = "\n".join(log_messages)
    assert "RuntimeError" in log_text
    assert "provider-token" not in log_text
    assert "hunter2" not in log_text
    assert "data:image/png;base64" not in log_text


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
