"""Image generation provider wrapper tests."""

from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import MissingOpenAIKeyError, get_settings
from app.services import image_generation_service
from app.services.image_generation_service import ImageGenerationProviderError


def _png_bytes(size: tuple[int, int] = (1, 1), color: tuple[int, int, int] = (20, 120, 180)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_1X1 = _png_bytes()


def _write_image(path) -> None:
    path.write_bytes(PNG_1X1)


def test_missing_openai_key_raises_controlled_configuration_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "put_openai_key_here")
    get_settings.cache_clear()

    with pytest.raises(MissingOpenAIKeyError) as exc_info:
        image_generation_service.generate_fabric_on_user_photo("/tmp/missing.png", "/tmp/missing-texture.png", "prompt")

    assert "OpenAI API key" in str(exc_info.value)


def test_user_photo_generation_uses_openai_sdk_config_and_closes_files(tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    _write_image(user_photo)
    _write_image(texture)
    captured: dict[str, object] = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG_1X1).decode("ascii"))])

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    monkeypatch.setenv("OPENAI_IMAGE_SIZE", "1024x1536")
    monkeypatch.setenv("OPENAI_IMAGE_QUALITY", "medium")
    monkeypatch.setenv("OPENAI_IMAGE_OUTPUT_FORMAT", "png")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    result = image_generation_service.generate_fabric_on_user_photo(str(user_photo), str(texture), "visible garment")

    assert result == PNG_1X1
    assert captured["model"] == "gpt-image-1"
    assert captured["prompt"] == "visible garment"
    assert captured["size"] == "1024x1536"
    assert captured["quality"] == "medium"
    assert captured["output_format"] == "png"
    assert "mask" not in captured
    images = captured["image"]
    assert len(images) == 2
    assert all(image.closed for image in images)


def test_user_photo_generation_can_send_optional_mask(tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    mask = tmp_path / "mask.png"
    for path in (user_photo, texture, mask):
        _write_image(path)
    captured: dict[str, object] = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG_1X1).decode("ascii"))])

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    result = image_generation_service.generate_fabric_on_user_photo(
        str(user_photo),
        str(texture),
        "masked clothing",
        mask_image_path=str(mask),
    )

    assert result == PNG_1X1
    assert "mask" in captured
    assert captured["mask"].closed
    assert all(image.closed for image in captured["image"])


def test_user_photo_generation_can_override_provider_size_per_call(tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    _write_image(user_photo)
    _write_image(texture)
    captured: dict[str, object] = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG_1X1).decode("ascii"))])

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    monkeypatch.setenv("OPENAI_IMAGE_SIZE", "1024x1536")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    result = image_generation_service.generate_fabric_on_user_photo(
        str(user_photo),
        str(texture),
        "visible garment",
        image_size="auto",
    )

    assert result == PNG_1X1
    assert captured["size"] == "auto"


def test_user_photo_generation_sends_input_fidelity_for_supported_model(tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    _write_image(user_photo)
    _write_image(texture)
    captured: dict[str, object] = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG_1X1).decode("ascii"))])

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    result = image_generation_service.generate_fabric_on_user_photo(
        str(user_photo),
        str(texture),
        "preserve protected regions",
        input_fidelity="high",
    )

    assert result == PNG_1X1
    assert captured["input_fidelity"] == "high"


def test_user_photo_generation_omits_input_fidelity_for_unsupported_model(tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    _write_image(user_photo)
    _write_image(texture)
    captured: dict[str, object] = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG_1X1).decode("ascii"))])

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    result = image_generation_service.generate_fabric_on_user_photo(
        str(user_photo),
        str(texture),
        "preserve protected regions",
        input_fidelity="high",
    )

    assert result == PNG_1X1
    assert "input_fidelity" not in captured


def test_catalog_style_generation_can_send_mask(tmp_path, monkeypatch) -> None:
    base = tmp_path / "base.png"
    texture = tmp_path / "texture.png"
    mask = tmp_path / "mask.png"
    for path in (base, texture, mask):
        _write_image(path)
    captured: dict[str, object] = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG_1X1).decode("ascii"))])

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    result = image_generation_service.generate_fabric_on_catalog_style(str(base), str(texture), str(mask), "prompt")

    assert result == PNG_1X1
    assert "mask" in captured
    assert captured["mask"].closed
    assert len(captured["image"]) == 2


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(data=[]),
        SimpleNamespace(data=[SimpleNamespace(b64_json=None)]),
        SimpleNamespace(data=[SimpleNamespace(b64_json="not-valid-base64")]),
        {"data": [{"b64_json": "not-valid-base64"}]},
    ],
)
def test_provider_bad_response_is_controlled(response, tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    _write_image(user_photo)
    _write_image(texture)

    class FakeImages:
        def edit(self, **kwargs):
            return response

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    with pytest.raises(ImageGenerationProviderError) as exc_info:
        image_generation_service.generate_fabric_on_user_photo(str(user_photo), str(texture), "prompt")

    assert "sk-test-provider" not in str(exc_info.value)
    assert "data:image" not in str(exc_info.value)


def test_provider_exception_is_sanitized(tmp_path, monkeypatch) -> None:
    user_photo = tmp_path / "user-photo.png"
    texture = tmp_path / "texture.png"
    _write_image(user_photo)
    _write_image(texture)

    class FakeImages:
        def edit(self, **kwargs):
            raise RuntimeError(
                "Authorization: Bearer sk-provider-secret password=hunter2 data:image/png;base64,"
                + "A" * 120
            )

    class FakeClient:
        images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider")
    get_settings.cache_clear()
    monkeypatch.setattr(image_generation_service, "_create_openai_client", lambda _api_key: FakeClient())

    with pytest.raises(ImageGenerationProviderError) as exc_info:
        image_generation_service.generate_fabric_on_user_photo(str(user_photo), str(texture), "prompt")

    message = str(exc_info.value)
    assert "sk-provider-secret" not in message
    assert "hunter2" not in message
    assert "data:image/png;base64" not in message
