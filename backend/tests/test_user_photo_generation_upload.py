"""User-photo generation upload validation tests."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageChops, ImageDraw
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage
from app.models.generation import Generation
from app.models.telegram_user import TelegramUser
from app.services.mask_service import (
    INVALID_MASK_PRESET_MESSAGE,
    MASK_PRESET_CENTRAL_UPPER_GARMENT,
    MASK_PRESET_VISIBLE_INNER_TSHIRT,
    MASK_PROVIDER_NOT_CONFIGURED_MESSAGE,
    STRICT_MASK_REQUIRED_MESSAGE,
    calculate_edit_coverage,
)
from app.services.preservation_service import (
    PRESERVATION_FAILURE_MESSAGE,
    PreservationCheckResult,
    PreservationThresholds,
    UserPhotoPreservationError,
)

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}
WRONG_BOT_HEADERS = {"X-Bot-Token": "wrong"}


def _png_bytes(size: tuple[int, int] = (1, 1), color: tuple[int, int, int] = (20, 120, 180)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_1X1 = _png_bytes()
PNG_300 = _png_bytes(size=(300, 300))


def _open_overshirt_source_bytes(size: tuple[int, int] = (300, 300)) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", size, color=(35, 42, 48))
    draw = ImageDraw.Draw(image)
    width, height = size
    # Background, head, hands, and a saturated overshirt should stay protected.
    draw.ellipse((120, 18, 180, 78), fill=(190, 145, 115))
    draw.rectangle((55, 95, 118, 236), fill=(22, 140, 72))
    draw.rectangle((182, 95, 245, 236), fill=(22, 140, 72))
    draw.rectangle((70, 180, 108, 230), fill=(190, 145, 115))
    draw.rectangle((192, 180, 230, 230), fill=(190, 145, 115))
    # Light neutral inner T-shirt, intentionally central.
    draw.polygon(
        [
            (124, 104),
            (176, 104),
            (191, 160),
            (184, 232),
            (116, 232),
            (109, 160),
        ],
        fill=(226, 224, 216),
    )
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _visible_inner_tshirt_smoke_source_bytes() -> bytes:
    """Return the same synthetic shape used by the preset preflight smoke."""

    buffer = BytesIO()
    width, height = 768, 1024
    image = Image.new("RGB", (width, height), (38, 44, 50))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 820, width - 1, height - 1), fill=(56, 56, 58))
    draw.rectangle((90, 90, 678, 920), outline=(90, 95, 100), width=8)
    draw.ellipse((318, 92, 450, 224), fill=(198, 150, 120), outline=(40, 40, 40), width=3)
    draw.rectangle((300, 224, 468, 300), fill=(198, 150, 120))
    draw.polygon(
        [(292, 300), (476, 300), (540, 505), (492, 825), (276, 825), (228, 505)],
        fill=(232, 231, 224),
        outline=(120, 120, 115),
    )
    draw.polygon([(195, 290), (306, 260), (292, 825), (145, 815)], fill=(30, 126, 70), outline=(20, 85, 50))
    draw.polygon([(573, 290), (462, 260), (476, 825), (623, 815)], fill=(30, 126, 70), outline=(20, 85, 50))
    draw.ellipse((488, 640, 620, 755), fill=(198, 150, 120), outline=(40, 40, 40))
    draw.ellipse((140, 455, 235, 590), fill=(198, 150, 120), outline=(40, 40, 40))
    draw.rectangle((520, 438, 582, 625), fill=(18, 18, 20))
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _mask_bytes(size: tuple[int, int] = (300, 300), box: tuple[int, int, int, int] = (75, 75, 225, 225)) -> bytes:
    buffer = BytesIO()
    mask = Image.new("RGBA", size, color=(0, 0, 0, 255))
    ImageDraw.Draw(mask).rectangle(box, fill=(0, 0, 0, 0))
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def _provider_output_changing_only_mask(user_photo_path: str, mask_image_path: str, color=(180, 30, 180)) -> bytes:
    with Image.open(user_photo_path) as base_image, Image.open(mask_image_path) as mask_image:
        candidate = base_image.convert("RGB")
        alpha = mask_image.convert("RGBA").getchannel("A")
        pixels = candidate.load()
        for y in range(candidate.height):
            for x in range(candidate.width):
                if alpha.getpixel((x, y)) < 128:
                    pixels[x, y] = color
    buffer = BytesIO()
    candidate.save(buffer, format="PNG")
    return buffer.getvalue()


def _provider_output_changing_protected_region(user_photo_path: str, mask_image_path: str) -> bytes:
    with Image.open(user_photo_path) as base_image:
        candidate = base_image.convert("RGB")
    draw = ImageDraw.Draw(candidate)
    draw.rectangle((0, 0, candidate.width - 1, max(1, candidate.height // 5)), fill=(250, 20, 20))
    buffer = BytesIO()
    candidate.save(buffer, format="PNG")
    return buffer.getvalue()


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _write_upload(relative_url: str) -> None:
    path = get_settings().upload_dir / relative_url.removeprefix("/uploads/")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (300, 300), color=(40, 120, 190)).save(path, format="PNG")


def _create_fabric(
    with_texture: bool = True,
    status: str = "published",
    *,
    with_main: bool = False,
    sku: str | None = None,
    name: str = "User photo fabric",
    category: str = "cotton",
    color: str | None = None,
) -> str:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=sku or f"PHOTO-{uuid4().hex[:10]}",
            name=name,
            category=category,
            color=color,
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Тестовая ткань для user-photo generation.",
            status=status,
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        if with_main:
            image_url = f"/uploads/fabrics/{uuid4().hex}-main.png"
            _write_upload(image_url)
            db.add(FabricImage(fabric_id=fabric.id, image_url=image_url, image_type="main", sort_order=0))
        if with_texture:
            image_url = f"/uploads/fabrics/{uuid4().hex}-texture.png"
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
    mask_content: bytes | None = None,
    mask_content_type: str = "image/png",
    input_mode: str | None = None,
    mask_preset: str | None = None,
):
    data = {"fabric_id": fabric_id}
    if telegram_id is not None:
        data["telegram_id"] = str(telegram_id)
    if input_mode is not None:
        data["input_mode"] = input_mode
    if mask_preset is not None:
        data["mask_preset"] = mask_preset
    files = {"photo": ("photo.png", content, content_type)}
    if mask_content is not None:
        files["mask"] = ("mask.png", mask_content, mask_content_type)
    return client.post(
        "/api/generations/user-photo",
        headers=headers,
        data=data,
        files=files,
    )


def _allow_legacy_no_mask_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "off")
    monkeypatch.setenv("USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT", "false")
    get_settings.cache_clear()


def _fabric_reference_path(fabric_id: str, image_type: str) -> str:
    with SessionLocal() as db:
        image = db.scalar(
            select(FabricImage).where(FabricImage.fabric_id == UUID(fabric_id), FabricImage.image_type == image_type)
        )
        assert image is not None
        return str(get_settings().upload_dir / image.image_url.removeprefix("/uploads/"))


def _remove_fabric_reference_file(fabric_id: str, image_type: str) -> str:
    path = Path(_fabric_reference_path(fabric_id, image_type))
    path.unlink()
    return str(path)


def _set_fabric_reference_url(fabric_id: str, image_type: str, image_url: str) -> None:
    with SessionLocal() as db:
        image = db.scalar(
            select(FabricImage).where(FabricImage.fabric_id == UUID(fabric_id), FabricImage.image_type == image_type)
        )
        assert image is not None
        image.image_url = image_url
        db.add(image)
        db.commit()


def test_user_photo_generation_default_requires_mask_before_provider(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    provider_called = False

    def fake_generate(
        user_photo_path: str,
        fabric_texture_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == STRICT_MASK_REQUIRED_MESSAGE
    assert provider_called is False
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["mode"] == "user_photo"
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["user_photo_url"].startswith("/uploads/user-photos/")
    assert admin_generation["mask_image_url"] is None
    assert admin_generation["error_message"] == STRICT_MASK_REQUIRED_MESSAGE


def test_user_photo_generation_garment_crop_mode_sends_only_crop_to_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric(sku="PHOTO-CROP", name="Crop fabric", category="wool")
    telegram_id = _create_telegram_user()
    expected_reference_path = _fabric_reference_path(fabric_id, "texture")
    captured: dict[str, str | None] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["provider_input_path"] = user_photo_path
        captured["fabric_reference_path"] = fabric_reference_path
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        assert Path(user_photo_path).parent.name == "user-garment-crops"
        assert fabric_reference_path == expected_reference_path
        assert mask_image_path is None
        assert "cropped garment image" in prompt
        assert "not a full person photo" in prompt
        assert "Do not create a person" in prompt
        return PNG_300

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(
        client,
        fabric_id,
        PNG_300,
        "image/png",
        BOT_HEADERS,
        telegram_id=telegram_id,
        input_mode="garment_crop",
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mode"] == "user_photo_garment_crop"
    assert payload["fabric_id"] == fabric_id
    assert payload["user_photo_url"].startswith("/uploads/user-garment-crops/")
    assert payload["mask_image_url"] is None
    assert payload["result_image_url"].startswith("/uploads/generations/")
    assert captured["provider_input_path"]
    assert Path(captured["provider_input_path"] or "").exists()

    admin_response = client.get("/api/admin/generations?status=completed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["id"] == payload["id"]
    assert admin_generation["mode"] == "user_photo_garment_crop"
    assert admin_generation["telegram_user"]["telegram_id"] == telegram_id
    assert admin_generation["user_photo_url"] == payload["user_photo_url"]


def test_user_photo_generation_garment_crop_mode_rejects_mask(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    provider_called = False

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_300

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(
        client,
        fabric_id,
        PNG_300,
        "image/png",
        BOT_HEADERS,
        input_mode="garment_crop",
        mask_content=_mask_bytes(),
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Garment crop mode does not accept a full-photo mask."
    assert provider_called is False


def test_user_photo_generation_preset_mask_calls_provider_with_mask(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    telegram_id = _create_telegram_user()
    captured: dict[str, str | None] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["mask_image_path"] = mask_image_path
        captured["prompt"] = prompt
        with Image.open(user_photo_path) as provider_input:
            captured["provider_input_size"] = f"{provider_input.width}x{provider_input.height}"
        with Image.open(mask_image_path) as provider_mask:
            captured["provider_mask_size"] = f"{provider_mask.width}x{provider_mask.height}"
        assert mask_image_path is not None
        captured["mask_exists_during_call"] = str(Path(mask_image_path).exists())
        return _provider_output_changing_only_mask(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(
        client,
        fabric_id,
        PNG_300,
        "image/png",
        BOT_HEADERS,
        telegram_id=telegram_id,
        mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mask_image_url"].startswith("/uploads/user-photo-masks/")
    assert captured["mask_image_path"]
    assert captured["mask_exists_during_call"] == "True"
    assert captured["provider_input_size"] == "300x300"
    assert captured["provider_mask_size"] == "300x300"
    assert "A clothing edit mask is provided" in (captured["prompt"] or "")
    assert "Return the full-frame edited original photo" in (captured["prompt"] or "")
    assert "rectangular patch" in (captured["prompt"] or "")
    assert payload["result_image_url"].startswith("/uploads/generations/")
    persisted_mask_path = get_settings().upload_dir / payload["mask_image_url"].removeprefix("/uploads/")
    assert calculate_edit_coverage(persisted_mask_path) == pytest.approx(11.5, abs=0.5)
    with Image.open(get_settings().upload_dir / payload["result_image_url"].removeprefix("/uploads/")) as result_image:
        assert result_image.size == (300, 300)

    admin_response = client.get("/api/admin/generations?status=completed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["id"] == payload["id"]
    assert admin_generation["telegram_user"]["telegram_id"] == telegram_id
    assert admin_generation["mask_image_url"] == payload["mask_image_url"]


def test_user_photo_generation_visible_inner_tshirt_preset_uses_narrow_mask_and_normalized_reference(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    captured: dict[str, str | None] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["fabric_reference_path"] = fabric_reference_path
        captured["mask_image_path"] = mask_image_path
        captured["prompt"] = prompt
        assert mask_image_path is not None
        with Image.open(fabric_reference_path) as reference:
            captured["fabric_reference_size"] = f"{reference.width}x{reference.height}"
        with Image.open(mask_image_path) as mask:
            alpha = mask.convert("RGBA").getchannel("A")
            # Inner T-shirt center is editable; saturated overshirt, face, and hand regions are protected.
            assert alpha.getpixel((150, 150)) < 128
            assert alpha.getpixel((85, 150)) >= 128
            assert alpha.getpixel((150, 45)) >= 128
            assert alpha.getpixel((90, 205)) >= 128
        return _provider_output_changing_only_mask(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(
        client,
        fabric_id,
        _open_overshirt_source_bytes(),
        "image/png",
        BOT_HEADERS,
        mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert captured["mask_image_path"]
    assert Path(captured["fabric_reference_path"] or "").name == "fabric_reference_normalized.png"
    assert captured["fabric_reference_size"] == "1024x1024"
    assert "fabric_reference_normalized.png" not in (captured["prompt"] or "")
    persisted_mask_path = get_settings().upload_dir / payload["mask_image_url"].removeprefix("/uploads/")
    coverage = calculate_edit_coverage(persisted_mask_path)
    assert 3.0 <= coverage <= 20.0


def test_user_photo_generation_local_texture_transfer_completes_without_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    source_bytes = _visible_inner_tshirt_smoke_source_bytes()
    provider_called = False
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "local_texture_transfer")
    monkeypatch.setenv("TRYON_DEBUG_BUNDLE_ENABLED", "true")
    get_settings.cache_clear()

    def fail_provider(*args, **kwargs) -> bytes:
        nonlocal provider_called
        provider_called = True
        raise AssertionError("local_texture_transfer must not call provider")

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fail_provider)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            source_bytes,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        monkeypatch.delenv("TRYON_DEBUG_BUNDLE_ENABLED", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result_image_url"].startswith("/uploads/generations/")
    assert provider_called is False

    original = Image.open(BytesIO(source_bytes)).convert("RGB")
    result_path = get_settings().upload_dir / payload["result_image_url"].removeprefix("/uploads/")
    mask_path = get_settings().upload_dir / payload["mask_image_url"].removeprefix("/uploads/")
    with Image.open(result_path) as result_image, Image.open(mask_path) as mask_image:
        result = result_image.convert("RGB")
        assert result.size == original.size
        alpha = mask_image.convert("RGBA").getchannel("A")
        diff = ImageChops.difference(original, result)
        diff_pixels = diff.load()
        alpha_pixels = alpha.load()
        outside_changed = 0
        inside_changed = 0
        for y in range(result.height):
            for x in range(result.width):
                if max(diff_pixels[x, y]) > 0:
                    if alpha_pixels[x, y] < 128:
                        inside_changed += 1
                    else:
                        outside_changed += 1
    assert inside_changed > 0
    assert outside_changed == 0

    report_path = get_settings().upload_dir / "tryon-debug" / f"{payload['id']}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    [attempt] = report["attempts"]
    assert report["strategy"] == "local_texture_transfer"
    assert attempt["strategy"] == "local_texture_transfer"
    assert attempt["provider_called"] is False
    assert attempt["provider_attempts"] == 0
    assert attempt["preservation_checked"] is True
    assert attempt["guardrail_status"] == "passed"
    metadata = attempt["local_texture_transfer_metadata"]
    assert metadata["provider_called"] is False
    assert metadata["outside_mask_mean_delta"] == 0
    assert metadata["outside_mask_changed_pixel_percent"] == 0
    assert metadata["hard_mask_coverage_percent"] >= 3.0
    assert metadata["tile_size"] >= 32


def test_user_photo_generation_local_texture_transfer_fail_keeps_result_absent(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "local_texture_transfer")
    get_settings.cache_clear()

    def fail_provider(*args, **kwargs) -> bytes:
        raise AssertionError("local_texture_transfer must not call provider")

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> None:
        raise UserPhotoPreservationError(
            PreservationCheckResult(
                passes=False,
                reason="protected_region_drift",
                message=PRESERVATION_FAILURE_MESSAGE,
                thresholds=PreservationThresholds(),
                original_size=(768, 1024),
                provider_output_size=(768, 1024),
                mask_size=(768, 1024),
                aspect_ratio_delta=0.0,
                size_normalized=False,
                normalized_size=None,
            )
        )

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fail_provider)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            _visible_inner_tshirt_smoke_source_bytes(),
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result_image_url"] is None
    assert payload["error_message"] == PRESERVATION_FAILURE_MESSAGE


def test_user_photo_generation_vision_guided_edit_sends_full_photo_and_reference_without_provider_mask(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    captured: dict[str, str | None] = {}
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "vision_guided_edit")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
    ) -> bytes:
        captured["user_photo_path"] = user_photo_path
        captured["fabric_reference_path"] = fabric_reference_path
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        captured["image_size"] = image_size
        with Image.open(user_photo_path) as provider_input:
            captured["provider_input_size"] = f"{provider_input.width}x{provider_input.height}"
        with Image.open(fabric_reference_path) as reference:
            captured["fabric_reference_size"] = f"{reference.width}x{reference.height}"
        return PNG_300

    preservation_called: dict[str, str | None] = {}

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> None:
        preservation_called["source_image_path"] = str(source_image_path)
        preservation_called["mask_image_path"] = str(mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            _open_overshirt_source_bytes(),
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result_image_url"].startswith("/uploads/generations/")
    assert payload["mask_image_url"].startswith("/uploads/user-photo-masks/")
    assert captured["mask_image_path"] is None
    assert captured["image_size"] == "1024x1024"
    assert Path(captured["user_photo_path"] or "").parent.name == "user-photos"
    assert Path(captured["fabric_reference_path"] or "").name == "fabric_reference_normalized.png"
    assert captured["provider_input_size"] == "300x300"
    assert captured["fabric_reference_size"] == "1024x1024"
    assert preservation_called["mask_image_path"]
    prompt = captured["prompt"] or ""
    assert "edit the first image" in prompt
    assert "fabric/material reference" in prompt
    assert "visible inner T-shirt under the open overshirt/jacket" in prompt
    assert "Do not create a new person" in prompt
    assert "Do not create a new shirt" in prompt
    assert "Do not paste a rectangle" in prompt
    assert "collage" in prompt
    assert "mockup" in prompt
    assert "same square 1:1 aspect ratio" in prompt
    assert "Do not change canvas size" in prompt
    assert "do not crop" in prompt
    assert "do not add padding" in prompt


def test_vision_guided_provider_size_canvas_adapts_unsupported_portrait_aspect(tmp_path, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    source = tmp_path / "portrait-3x4.png"
    Image.new("RGB", (768, 1024), color=(40, 50, 60)).save(source)
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    get_settings.cache_clear()

    try:
        provider_size = generation_routes._select_vision_guided_provider_size(source)
        prompt = generation_routes._build_vision_guided_user_photo_prompt(
            Fabric(
                id=uuid4(),
                sku="HQ-FABRIC-R2-047",
                name="Test fabric",
                status="published",
            ),
            mask_mode=f"preset:{MASK_PRESET_VISIBLE_INNER_TSHIRT}",
            provider_size=provider_size,
        )
    finally:
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        get_settings.cache_clear()

    assert provider_size.original_size == (768, 1024)
    assert provider_size.requested_size == "1024x1536"
    assert provider_size.requested_aspect == "2:3"
    assert provider_size.exact_aspect_supported is False
    assert provider_size.canvas_adapted is True
    assert provider_size.provider_canvas_size == (1024, 1536)
    assert provider_size.source_box == (128, 256, 896, 1280)
    assert provider_size.original_aspect == 0.75
    assert "original portrait 768x1024 photo is centered inside" in prompt
    assert "neutral 1024x1536 provider canvas" in prompt
    assert "Do not move, crop, zoom, stretch, replace, or reframe the person/photo region" in prompt
    assert "only a compatibility canvas" in prompt


def test_vision_guided_canvas_adapter_extracts_original_frame(tmp_path, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    source = tmp_path / "portrait-3x4.png"
    source_image = Image.new("RGB", (768, 1024), color=(40, 50, 60))
    ImageDraw.Draw(source_image).rectangle((260, 360, 500, 760), fill=(210, 210, 200))
    source_image.save(source)
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    get_settings.cache_clear()

    try:
        provider_size = generation_routes._select_vision_guided_provider_size(source)
        provider_photo_path = generation_routes._prepare_vision_guided_provider_photo(source, provider_size, tmp_path)
    finally:
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        get_settings.cache_clear()

    with Image.open(provider_photo_path) as provider_input:
        assert provider_input.size == (1024, 1536)
        assert provider_input.getpixel((0, 0)) == (245, 245, 245)
        assert provider_input.crop(provider_size.source_box).size == (768, 1024)

    # Simulate a provider that preserves the padded canvas and edits only the centered photo region.
    with Image.open(provider_photo_path) as provider_input:
        provider_output = provider_input.convert("RGB")
    draw = ImageDraw.Draw(provider_output)
    draw.rectangle((388, 616, 636, 760), fill=(160, 60, 180))
    buffer = BytesIO()
    provider_output.save(buffer, format="PNG")

    extracted = generation_routes._extract_vision_guided_original_frame(buffer.getvalue(), provider_size)
    with Image.open(BytesIO(extracted)) as extracted_image:
        assert extracted_image.size == (768, 1024)


def test_user_photo_generation_vision_guided_canvas_adapter_keeps_guardrail_on_original_frame(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    source_bytes = _visible_inner_tshirt_smoke_source_bytes()
    captured: dict[str, object] = {}
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "vision_guided_edit")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
    ) -> bytes:
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        captured["image_size"] = image_size
        with Image.open(user_photo_path) as provider_input:
            captured["provider_input_size"] = provider_input.size
            provider_output = provider_input.convert("RGB")
        # Edit only the known centered original-photo region so extraction can return a 768x1024 frame.
        ImageDraw.Draw(provider_output).polygon(
            [
                (448, 360),
                (576, 360),
                (600, 520),
                (584, 760),
                (440, 760),
                (424, 520),
            ],
            fill=(140, 45, 170),
        )
        buffer = BytesIO()
        provider_output.save(buffer, format="PNG")
        return buffer.getvalue()

    preservation_called: dict[str, object] = {}

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> None:
        preservation_called["source_image_path"] = str(source_image_path)
        preservation_called["mask_image_path"] = str(mask_image_path)
        with Image.open(source_image_path) as source_image, Image.open(BytesIO(candidate_image_bytes)) as candidate_image:
            preservation_called["source_size"] = source_image.size
            preservation_called["candidate_size"] = candidate_image.size

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            source_bytes,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert captured["mask_image_path"] is None
    assert captured["image_size"] == "1024x1536"
    assert captured["provider_input_size"] == (1024, 1536)
    assert preservation_called["source_size"] == (768, 1024)
    assert preservation_called["candidate_size"] == (768, 1024)
    assert preservation_called["mask_image_path"]
    prompt = str(captured["prompt"])
    assert "neutral 1024x1536 provider canvas" in prompt
    assert "compatibility canvas" in prompt


def test_user_photo_generation_masked_edit_canvas_adapter_aligns_photo_and_mask(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    source_bytes = _visible_inner_tshirt_smoke_source_bytes()
    captured: dict[str, object] = {}
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "chatgpt_like_masked_edit")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    monkeypatch.setenv("TRYON_INPUT_FIDELITY", "high")
    monkeypatch.setenv("TRYON_DEBUG_BUNDLE_ENABLED", "true")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
        input_fidelity: str | None = None,
    ) -> bytes:
        assert mask_image_path is not None
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        captured["image_size"] = image_size
        captured["input_fidelity"] = input_fidelity
        with Image.open(user_photo_path) as provider_input, Image.open(mask_image_path) as provider_mask:
            captured["provider_input_size"] = provider_input.size
            captured["provider_mask_size"] = provider_mask.size
            mask_alpha = provider_mask.convert("RGBA").getchannel("A")
            captured["mask_padding_alpha"] = mask_alpha.getpixel((0, 0))
            captured["mask_edit_alpha"] = mask_alpha.getpixel((512, 720))
            provider_output = provider_input.convert("RGB")
        # Edit only inside the centered source frame. The route should extract
        # that 768x1024 frame before running preservation guardrails.
        ImageDraw.Draw(provider_output).polygon(
            [
                (448, 616),
                (576, 616),
                (600, 760),
                (584, 1040),
                (440, 1040),
                (424, 760),
            ],
            fill=(140, 45, 170),
        )
        buffer = BytesIO()
        provider_output.save(buffer, format="PNG")
        return buffer.getvalue()

    preservation_called: dict[str, object] = {}

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> None:
        preservation_called["source_image_path"] = str(source_image_path)
        preservation_called["mask_image_path"] = str(mask_image_path)
        with Image.open(source_image_path) as source_image, Image.open(BytesIO(candidate_image_bytes)) as candidate_image:
            preservation_called["source_size"] = source_image.size
            preservation_called["candidate_size"] = candidate_image.size

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            source_bytes,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        monkeypatch.delenv("TRYON_INPUT_FIDELITY", raising=False)
        monkeypatch.delenv("TRYON_DEBUG_BUNDLE_ENABLED", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert captured["image_size"] == "1024x1536"
    assert captured["input_fidelity"] == "high"
    assert captured["provider_input_size"] == (1024, 1536)
    assert captured["provider_mask_size"] == (1024, 1536)
    assert captured["mask_padding_alpha"] == 255
    assert captured["mask_edit_alpha"] == 0
    assert preservation_called["source_size"] == (768, 1024)
    assert preservation_called["candidate_size"] == (768, 1024)
    assert preservation_called["mask_image_path"]
    prompt = str(captured["prompt"])
    assert "provider compatibility canvas" in prompt
    assert "Do not edit the neutral padding" in prompt
    assert "Treat every opaque/protected mask pixel as locked source photography" in prompt
    report_path = get_settings().upload_dir / "tryon-debug" / f"{payload['id']}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    [attempt] = report["attempts"]
    assert attempt["provider_model"] == "gpt-image-1"
    assert attempt["endpoint_method"] == "images.edit"
    assert attempt["input_image_count"] == 2
    assert attempt["first_input_role"] == "original_user_photo"
    assert attempt["second_input_role"] == "fabric_reference"
    assert attempt["mask_applied_to_first_input"] is True
    assert attempt["input_fidelity_requested"] == "high"
    assert attempt["input_fidelity_applied"] == "high"
    assert attempt["input_fidelity_supported"] is True


def test_vision_guided_provider_size_uses_exact_size_for_gpt_image_2(tmp_path, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    source = tmp_path / "portrait-3x4.png"
    Image.new("RGB", (768, 1024), color=(40, 50, 60)).save(source)
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    get_settings.cache_clear()

    try:
        provider_size = generation_routes._select_vision_guided_provider_size(source)
    finally:
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        get_settings.cache_clear()

    assert provider_size.original_size == (768, 1024)
    assert provider_size.requested_size == "768x1024"
    assert provider_size.requested_aspect == "3:4"
    assert provider_size.exact_aspect_supported is True


def test_user_photo_generation_masked_edit_omits_input_fidelity_for_gpt_image_2(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    source_bytes = _visible_inner_tshirt_smoke_source_bytes()
    captured: dict[str, object] = {}
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "chatgpt_like_masked_edit")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setenv("TRYON_INPUT_FIDELITY", "high")
    monkeypatch.setenv("TRYON_DEBUG_BUNDLE_ENABLED", "true")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
        input_fidelity: str | None = None,
    ) -> bytes:
        assert mask_image_path is not None
        captured["image_size"] = image_size
        captured["input_fidelity"] = input_fidelity
        with Image.open(user_photo_path) as provider_input:
            captured["provider_input_size"] = provider_input.size
            provider_output = provider_input.convert("RGB")
        ImageDraw.Draw(provider_output).polygon(
            [
                (320, 305),
                (448, 305),
                (492, 510),
                (468, 825),
                (300, 825),
                (276, 510),
            ],
            fill=(90, 35, 150),
        )
        buffer = BytesIO()
        provider_output.save(buffer, format="PNG")
        return buffer.getvalue()

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> None:
        return None

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            source_bytes,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_VISIBLE_INNER_TSHIRT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        monkeypatch.delenv("TRYON_INPUT_FIDELITY", raising=False)
        monkeypatch.delenv("TRYON_DEBUG_BUNDLE_ENABLED", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert captured["image_size"] == "768x1024"
    assert captured["provider_input_size"] == (768, 1024)
    assert captured["input_fidelity"] is None
    report_path = get_settings().upload_dir / "tryon-debug" / f"{payload['id']}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    [attempt] = report["attempts"]
    assert attempt["provider_model"] == "gpt-image-2"
    assert attempt["input_fidelity_requested"] == "high"
    assert attempt["input_fidelity_applied"] is None
    assert attempt["input_fidelity_supported"] is False
    assert attempt["input_fidelity_reason"] == "gpt_image_2_high_fidelity_automatic"


def test_user_photo_generation_vision_guided_edit_rejects_guardrail_failure_without_result(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "vision_guided_edit")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
    ) -> bytes:
        assert mask_image_path is None
        return _provider_output_changing_protected_region(user_photo_path, mask_image_path or user_photo_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result_image_url"] is None
    assert "сохранить исходное фото" in payload["error_message"]
    assert not any((get_settings().upload_dir / "generations").iterdir())


def test_user_photo_generation_saves_normalized_guardrail_output(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "vision_guided_edit")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
    ) -> bytes:
        assert mask_image_path is None
        return _png_bytes(size=(600, 600), color=(20, 120, 180))

    normalized_bytes = _png_bytes(size=(300, 300), color=(40, 140, 200))

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> PreservationCheckResult:
        return PreservationCheckResult(
            passes=True,
            reason=None,
            message="ok",
            thresholds=PreservationThresholds(),
            original_size=(300, 300),
            provider_output_size=(600, 600),
            mask_size=(300, 300),
            aspect_ratio_delta=0.0,
            size_normalized=True,
            normalized_size=(300, 300),
            normalized_candidate_image_bytes=normalized_bytes,
        )

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    result_path = get_settings().upload_dir / payload["result_image_url"].removeprefix("/uploads/")
    with Image.open(result_path) as result_image:
        assert result_image.size == (300, 300)


def test_user_photo_generation_vision_guided_edit_retries_until_guardrail_pass(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    calls: list[str] = []
    preservation_calls = 0
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "vision_guided_edit")
    monkeypatch.setenv("TRYON_MAX_PROVIDER_ATTEMPTS", "2")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
    ) -> bytes:
        assert mask_image_path is None
        calls.append(prompt)
        return PNG_300

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> PreservationCheckResult | None:
        nonlocal preservation_calls
        preservation_calls += 1
        if preservation_calls == 1:
            result = PreservationCheckResult(
                passes=False,
                reason="rectangular_overlay_detected",
                message=PRESERVATION_FAILURE_MESSAGE,
                thresholds=PreservationThresholds(),
            )
            raise UserPhotoPreservationError(result)
        return None

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        monkeypatch.delenv("TRYON_MAX_PROVIDER_ATTEMPTS", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert len(calls) == 2
    assert "Retry correction" not in calls[0]
    assert "Retry correction" in calls[1]
    assert preservation_calls == 2


def test_user_photo_generation_unknown_tryon_strategy_falls_back_to_masked_edit(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    captured: dict[str, str | None] = {}
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "not-a-real-strategy")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["mask_image_path"] = mask_image_path
        assert mask_image_path is not None
        return _provider_output_changing_only_mask(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
    assert captured["mask_image_path"]


def test_user_photo_generation_vision_guided_debug_metadata_is_sanitized(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    monkeypatch.setenv("TRYON_PROVIDER_STRATEGY", "vision_guided_edit")
    monkeypatch.setenv("TRYON_DEBUG_BUNDLE_ENABLED", "true")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
        image_size: str | None = None,
    ) -> bytes:
        assert mask_image_path is None
        return PNG_300

    def fake_preservation_safe(
        *,
        source_image_path: Path,
        candidate_image_bytes: bytes,
        mask_image_path: Path,
    ) -> None:
        result = PreservationCheckResult(
            passes=False,
            reason="rectangular_overlay_detected",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=PreservationThresholds(),
            original_size=(300, 300),
            provider_output_size=(1024, 1024),
            mask_size=(300, 300),
            aspect_ratio_delta=0.0,
            size_normalized=False,
            normalized_size=None,
        )
        raise UserPhotoPreservationError(result)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(generation_routes, "_ensure_user_photo_preservation_safe", fake_preservation_safe)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_PROVIDER_STRATEGY", raising=False)
        monkeypatch.delenv("TRYON_DEBUG_BUNDLE_ENABLED", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    report_path = get_settings().upload_dir / "tryon-debug" / f"{payload['id']}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    [attempt] = report["attempts"]
    assert report["strategy"] == "vision_guided_edit"
    assert attempt["strategy"] == "vision_guided_edit"
    assert attempt["prompt_version"] == "vision_guided_edit_v3_canvas_adapter"
    assert attempt["requested_provider_size"] == "1024x1024"
    assert attempt["requested_provider_aspect"] == "1:1"
    assert attempt["original_size"] == [300, 300]
    assert attempt["original_aspect"] == 1.0
    assert attempt["exact_provider_aspect_supported"] is True
    assert attempt["mask_used"] is False
    assert attempt["mask_mode"] == "none"
    assert attempt["guardrail_mask_mode"] == f"preset:{MASK_PRESET_CENTRAL_UPPER_GARMENT}"
    assert attempt["guardrail_reason"] == "rectangular_overlay_detected"
    assert attempt["guardrail_metadata"] == {
        "original_size": [300, 300],
        "provider_output_size": [1024, 1024],
        "mask_size": [300, 300],
        "original_aspect": 1.0,
        "provider_output_aspect": 1.0,
        "aspect_ratio_delta": 0.0,
        "size_normalized": False,
        "normalized_size": None,
        "fail_reason": "rectangular_overlay_detected",
    }
    serialized = json.dumps(report, ensure_ascii=False)
    assert "base64" not in serialized.lower()
    assert "OPENAI_API_KEY" not in serialized
    assert "BOT_INTERNAL_TOKEN" not in serialized
    assert "data:image" not in serialized


def test_user_photo_generation_retries_masked_edit_once_after_preservation_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    calls: list[str] = []
    monkeypatch.setenv("TRYON_MAX_PROVIDER_ATTEMPTS", "2")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        assert mask_image_path is not None
        calls.append(prompt)
        if len(calls) == 1:
            return _provider_output_changing_protected_region(user_photo_path, mask_image_path)
        return _provider_output_changing_only_mask(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_MAX_PROVIDER_ATTEMPTS", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result_image_url"].startswith("/uploads/generations/")
    assert len(calls) == 2
    assert "Retry correction" not in calls[0]
    assert "Retry correction" in calls[1]


def test_user_photo_generation_fails_after_bounded_masked_edit_attempts(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    calls = 0
    monkeypatch.setenv("TRYON_MAX_PROVIDER_ATTEMPTS", "2")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal calls
        calls += 1
        assert mask_image_path is not None
        return _provider_output_changing_protected_region(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
        )
    finally:
        monkeypatch.delenv("TRYON_MAX_PROVIDER_ATTEMPTS", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result_image_url"] is None
    assert calls == 2
    assert "сохранить исходное фото" in payload["error_message"]


def test_user_photo_generation_preset_mask_rejects_provider_protected_region_drift(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    telegram_id = _create_telegram_user()
    captured: dict[str, str | None] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["mask_image_path"] = mask_image_path
        assert mask_image_path is not None
        return _provider_output_changing_protected_region(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(
        client,
        fabric_id,
        PNG_300,
        "image/png",
        BOT_HEADERS,
        telegram_id=telegram_id,
        mask_preset=MASK_PRESET_CENTRAL_UPPER_GARMENT,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result_image_url"] is None
    assert payload["mask_image_url"].startswith("/uploads/user-photo-masks/")
    assert "сохранить исходное фото" in payload["error_message"]
    assert captured["mask_image_path"]


def test_user_photo_generation_invalid_mask_preset_fails_before_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    provider_called = False

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_300

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(
        client,
        fabric_id,
        PNG_300,
        "image/png",
        BOT_HEADERS,
        mask_preset="whole_person",
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == INVALID_MASK_PRESET_MESSAGE
    assert provider_called is False


def test_user_photo_generation_legacy_no_mask_mode_can_be_enabled_explicitly(
    client: TestClient,
    monkeypatch,
) -> None:
    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["mode"] == "user_photo"
    assert payload["fabric_id"] == fabric_id
    assert payload["user_photo_url"].startswith("/uploads/user-photos/")
    assert payload["status"] == "failed"
    assert "OpenAI API key" in payload["error_message"]


def test_user_photo_generation_requires_selected_fabric_id(client: TestClient) -> None:
    response = client.post(
        "/api/generations/user-photo",
        headers=BOT_HEADERS,
        files={"photo": ("photo.png", PNG_1X1, "image/png")},
    )

    assert response.status_code == 422, response.text
    with SessionLocal() as db:
        assert db.scalar(select(Generation)) is None


def test_user_photo_generation_requires_reference_image(client: TestClient) -> None:
    fabric_id = _create_fabric(with_texture=False)
    telegram_id = _create_telegram_user()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS, telegram_id=telegram_id)

    assert response.status_code == 400, response.text
    assert "изображения для примерки" in response.json()["detail"]
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
    assert "изображения для примерки" in admin_generation["error_message"]


def test_user_photo_generation_unpublished_fabric_persists_failed_record(client: TestClient) -> None:
    fabric_id = _create_fabric(status="draft")
    telegram_id = _create_telegram_user()

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS, telegram_id=telegram_id)

    assert response.status_code == 400, response.text
    assert "опубликован" in response.json()["detail"]
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

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric()

    def fake_generate(
        user_photo_path: str,
        fabric_texture_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        assert Path(user_photo_path).exists()
        assert Path(user_photo_path).parent.name == "user-photos"
        assert Path(fabric_texture_path).exists()
        assert mask_image_path is None
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
    assert admin_generation["mask_image_url"] is None
    assert admin_generation["fabric"]["sku"].startswith("PHOTO-")
    assert admin_generation["fabric"]["name"] == "User photo fabric"
    assert admin_generation["fabric"]["category"] == "cotton"


def test_user_photo_generation_mock_mask_mode_stores_and_sends_mask(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    captured: dict[str, str | None] = {}
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "mock")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["user_photo_path"] = user_photo_path
        captured["fabric_reference_path"] = fabric_reference_path
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        assert mask_image_path is not None
        return _provider_output_changing_only_mask(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(client, fabric_id, PNG_300, "image/png", BOT_HEADERS)
    finally:
        monkeypatch.delenv("USER_PHOTO_MASK_MODE", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mask_image_url"].startswith("/uploads/user-photo-masks/")
    assert captured["mask_image_path"]
    assert Path(captured["mask_image_path"] or "").exists()
    assert Path(captured["mask_image_path"] or "").parent.name == "user-photo-masks"
    assert "A clothing edit mask is provided" in (captured["prompt"] or "")
    assert "Preserve all non-editable regions exactly" in (captured["prompt"] or "")
    assert payload["result_image_url"].startswith("/uploads/generations/")


def test_user_photo_generation_provided_mask_mode_stores_and_sends_mask(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    captured: dict[str, str | None] = {}
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "provided")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["mask_image_path"] = mask_image_path
        captured["prompt"] = prompt
        assert mask_image_path is not None
        return _provider_output_changing_only_mask(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_content=_mask_bytes(),
        )
    finally:
        monkeypatch.delenv("USER_PHOTO_MASK_MODE", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mask_image_url"].startswith("/uploads/user-photo-masks/")
    assert captured["mask_image_path"]
    assert Path(captured["mask_image_path"] or "").exists()
    assert "A clothing edit mask is provided" in (captured["prompt"] or "")
    assert "strict inpainting/editing task" in (captured["prompt"] or "")
    assert "Do not change face, eyes, glasses" in (captured["prompt"] or "")


def test_user_photo_generation_provided_mask_rejects_protected_region_drift(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    log_messages: list[str] = []
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "provided")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        assert mask_image_path is not None
        return _provider_output_changing_protected_region(user_photo_path, mask_image_path)

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(
        generation_routes.logger,
        "warning",
        lambda message, *args: log_messages.append(message % args),
    )

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_content=_mask_bytes(),
        )
    finally:
        monkeypatch.delenv("USER_PHOTO_MASK_MODE", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result_image_url"] is None
    assert payload["mask_image_url"].startswith("/uploads/user-photo-masks/")
    assert "сохранить исходное фото" in payload["error_message"]
    assert not any((get_settings().upload_dir / "generations").iterdir())
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["id"] == payload["id"]
    assert admin_generation["result_image_url"] is None
    assert "сохранить исходное фото" in admin_generation["error_message"]
    log_text = "\n".join(log_messages)
    assert "preservation guardrail failed" in log_text
    assert "mean_delta=" in log_text
    assert str(get_settings().upload_dir) not in log_text
    assert "OPENAI_API_KEY" not in log_text
    assert "BOT_INTERNAL_TOKEN" not in log_text
    assert "data:image" not in log_text
    assert "base64" not in log_text


def test_user_photo_generation_provided_mask_rejects_size_mismatched_provider_output(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "provided")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        assert mask_image_path is not None
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_content=_mask_bytes(),
        )
    finally:
        monkeypatch.delenv("USER_PHOTO_MASK_MODE", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result_image_url"] is None
    assert "сохранить исходное фото" in payload["error_message"]
    assert not any((get_settings().upload_dir / "generations").iterdir())


def test_user_photo_generation_provided_mask_mode_requires_mask_before_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    provider_called = False
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "provided")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_300, "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == STRICT_MASK_REQUIRED_MESSAGE
    assert provider_called is False
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["mask_image_url"] is None
    assert admin_generation["error_message"] == STRICT_MASK_REQUIRED_MESSAGE


def test_user_photo_generation_provider_mode_does_not_fallback_to_no_mask(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    provider_called = False
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "provider")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_300, "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == MASK_PROVIDER_NOT_CONFIGURED_MESSAGE
    assert provider_called is False
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["mask_image_url"] is None
    assert admin_generation["error_message"] == MASK_PROVIDER_NOT_CONFIGURED_MESSAGE


def test_user_photo_generation_invalid_provided_mask_fails_controlled(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    fabric_id = _create_fabric()
    provider_called = False
    monkeypatch.setenv("USER_PHOTO_MASK_MODE", "provided")
    get_settings.cache_clear()

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    try:
        response = _post_user_photo(
            client,
            fabric_id,
            PNG_300,
            "image/png",
            BOT_HEADERS,
            mask_content=_mask_bytes(size=(20, 20), box=(2, 2, 10, 10)),
        )
    finally:
        monkeypatch.delenv("USER_PHOTO_MASK_MODE", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "User photo mask is not valid for editing."
    assert provider_called is False
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["mask_image_url"] is None
    assert "valid" in admin_generation["error_message"]


def test_user_photo_generation_uses_exact_requested_fabric_reference(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_a_id = _create_fabric(sku="PHOTO-A", name="Fabric A", category="linen")
    fabric_b_id = _create_fabric(sku="PHOTO-B", name="Fabric B", category="silk", color="emerald")
    expected_reference_path = _fabric_reference_path(fabric_b_id, "texture")
    captured: dict[str, str] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["user_photo_path"] = user_photo_path
        captured["fabric_reference_path"] = fabric_reference_path
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_b_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["fabric_id"] == fabric_b_id
    assert captured["user_photo_path"]
    assert captured["fabric_reference_path"] == expected_reference_path
    assert captured["mask_image_path"] is None
    assert fabric_a_id not in captured["prompt"]
    assert fabric_b_id in captured["prompt"]
    assert "PHOTO-B" in captured["prompt"]
    assert "Fabric B" in captured["prompt"]
    assert "selected catalog fabric reference image as the only fabric source" in captured["prompt"]
    assert "Preserve the exact same person" in captured["prompt"]
    assert "Do not change identity" in captured["prompt"]


def test_user_photo_generation_prefers_texture_over_main_reference(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric(with_main=True)
    expected_reference_path = _fabric_reference_path(fabric_id, "texture")
    captured: dict[str, str] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["fabric_reference_path"] = fabric_reference_path
        captured["mask_image_path"] = mask_image_path
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    assert captured["fabric_reference_path"] == expected_reference_path
    assert captured["mask_image_path"] is None


def test_user_photo_generation_falls_back_to_main_reference(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric(with_texture=False, with_main=True)
    expected_reference_path = _fabric_reference_path(fabric_id, "main")
    captured: dict[str, str] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["fabric_reference_path"] = fabric_reference_path
        captured["mask_image_path"] = mask_image_path
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    assert captured["fabric_reference_path"] == expected_reference_path
    assert captured["mask_image_path"] is None


def test_user_photo_generation_falls_back_to_same_fabric_main_when_texture_file_is_missing(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    other_fabric_id = _create_fabric(sku="PHOTO-OTHER", name="Other fabric", with_main=True)
    fabric_id = _create_fabric(sku="PHOTO-MAIN-FALLBACK", name="Main fallback fabric", with_main=True)
    _remove_fabric_reference_file(fabric_id, "texture")
    expected_reference_path = _fabric_reference_path(fabric_id, "main")
    other_reference_path = _fabric_reference_path(other_fabric_id, "texture")
    captured: dict[str, str] = {}

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        captured["user_photo_path"] = user_photo_path
        captured["fabric_reference_path"] = fabric_reference_path
        captured["prompt"] = prompt
        captured["mask_image_path"] = mask_image_path
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["fabric_id"] == fabric_id
    assert Path(captured["user_photo_path"]).exists()
    assert captured["fabric_reference_path"] == expected_reference_path
    assert captured["fabric_reference_path"] != other_reference_path
    assert captured["mask_image_path"] is None
    assert fabric_id in captured["prompt"]
    assert other_fabric_id not in captured["prompt"]


def test_user_photo_generation_missing_reference_files_fail_without_provider_or_fallback(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric(with_main=True)
    _remove_fabric_reference_file(fabric_id, "texture")
    _remove_fabric_reference_file(fabric_id, "main")
    telegram_id = _create_telegram_user()
    provider_called = False
    log_messages: list[str] = []

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)
    monkeypatch.setattr(
        generation_routes.logger,
        "warning",
        lambda message, *args: log_messages.append(message % args),
    )

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS, telegram_id=telegram_id)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Selected fabric has no usable reference image."
    assert provider_called is False
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["telegram_user"]["telegram_id"] == telegram_id
    assert admin_generation["user_photo_url"].startswith("/uploads/user-photos/")
    assert admin_generation["error_message"] == "Selected fabric has no usable reference image."
    log_text = "\n".join(log_messages)
    assert "Selected fabric has no AI-ready reference image" in log_text
    assert "OPENAI_API_KEY" not in log_text
    assert "BOT_INTERNAL_TOKEN" not in log_text
    assert "data:image" not in log_text
    assert "base64" not in log_text
    assert "PNG" not in log_text


@pytest.mark.parametrize("unsafe_url", ["https://example.com/fabric.png", "/uploads/../secret.png"])
def test_user_photo_generation_rejects_unsafe_reference_url_without_main_fallback(
    client: TestClient,
    monkeypatch,
    unsafe_url: str,
) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric(with_main=True)
    _set_fabric_reference_url(fabric_id, "texture", unsafe_url)
    provider_called = False

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_called
        provider_called = True
        return PNG_1X1

    monkeypatch.setattr(generation_routes.image_generation_service, "generate_fabric_on_user_photo", fake_generate)

    response = _post_user_photo(client, fabric_id, PNG_1X1, "image/png", BOT_HEADERS)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Selected fabric reference image URL is invalid."
    assert provider_called is False
    admin_response = client.get("/api/admin/generations?status=failed", headers=_admin_headers(client))
    assert admin_response.status_code == 200, admin_response.text
    [admin_generation] = admin_response.json()["items"]
    assert admin_generation["fabric_id"] == fabric_id
    assert admin_generation["error_message"] == "Selected fabric reference image URL is invalid."


def test_user_photo_generation_provider_error_is_normalized(client: TestClient, monkeypatch) -> None:
    from app.api.routes import generations as generation_routes

    _allow_legacy_no_mask_edit(monkeypatch)
    fabric_id = _create_fabric()
    log_messages: list[str] = []

    def fake_generate(
        user_photo_path: str,
        fabric_texture_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
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
