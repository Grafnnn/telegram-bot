"""Image generation integration isolated from API routes."""

from __future__ import annotations

import base64
from contextlib import ExitStack
from pathlib import Path
from typing import BinaryIO

from app.config import MissingOpenAIKeyError, get_settings
from app.utils.redaction import safe_exception_summary

IMAGE_ERROR = "AI-визуализация пока недоступна: OpenAI API key не настроен."
PROVIDER_ERROR = "AI-визуализация временно недоступна. Попробуйте позже."
IMAGE_EDIT_PROMPT = (
    "Replace only the fabric of the garment in the base image with the fabric texture from the reference image. "
    "Keep the exact silhouette, cut, seams, folds, pose, lighting, background and proportions. "
    "Preserve the garment construction and make the new fabric follow the folds naturally. "
    "Do not change the model's face, body, hair, background or accessories. "
    "Use the selected fabric realistically, including its color, pattern scale, texture and drape."
)
USER_PHOTO_EDIT_PROMPT = (
    "Edit the user photo as a realistic fashion fabric try-on. "
    "Use the selected catalog fabric reference image as the only material and texture source. "
    "Apply the selected fabric only to the visible garment or clothing area while preserving "
    "the person's identity, face, pose, body shape, background, lighting and garment silhouette. "
    "Do not change the face, hands, hair, body, camera angle, background, objects, room or accessories. "
    "Do not make the person nude. "
    "Do not add text, logos, watermarks, extra people or unrealistic artifacts. "
    "Preserve folds, seams, shadows and drape so only the clothing fabric changes."
)


class ImageGenerationProviderError(RuntimeError):
    """Raised for controlled provider failures that should not leak raw details."""


def _ensure_configured() -> str:
    settings = get_settings()
    if not settings.is_openai_configured:
        raise MissingOpenAIKeyError(IMAGE_ERROR)
    return settings.openai_api_key


def _create_openai_client(api_key: str):
    """Create an OpenAI SDK client lazily so tests can run without real calls."""

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - covered by dependency/CI install
        raise ImageGenerationProviderError("OpenAI SDK is not installed.") from exc
    settings = get_settings()
    return OpenAI(api_key=api_key, timeout=settings.openai_image_timeout_seconds)


def _value(container: object, key: str) -> object:
    if isinstance(container, dict):
        return container.get(key)
    return getattr(container, key, None)


def _extract_image_bytes(response: object) -> bytes:
    data = _value(response, "data")
    if not data:
        raise ImageGenerationProviderError(PROVIDER_ERROR)
    b64_json = _value(data[0], "b64_json")
    if not b64_json:
        raise ImageGenerationProviderError(PROVIDER_ERROR)
    try:
        image_bytes = base64.b64decode(b64_json, validate=True)
    except (ValueError, TypeError) as exc:
        raise ImageGenerationProviderError(PROVIDER_ERROR) from exc
    if not image_bytes:
        raise ImageGenerationProviderError(PROVIDER_ERROR)
    return image_bytes


def _edit_images(image_paths: list[str | Path], prompt: str, mask_image_path: str | Path | None = None) -> bytes:
    api_key = _ensure_configured()
    settings = get_settings()
    try:
        client = _create_openai_client(api_key)
        with ExitStack() as stack:
            images: list[BinaryIO] = [stack.enter_context(Path(path).open("rb")) for path in image_paths]
            kwargs = {
                "model": settings.openai_image_model,
                "image": images,
                "prompt": prompt,
                "size": settings.openai_image_size,
                "quality": settings.openai_image_quality,
                "output_format": settings.openai_image_output_format,
            }
            if mask_image_path:
                kwargs["mask"] = stack.enter_context(Path(mask_image_path).open("rb"))
            response = client.images.edit(**kwargs)
        return _extract_image_bytes(response)
    except MissingOpenAIKeyError:
        raise
    except ImageGenerationProviderError:
        raise
    except Exception as exc:
        raise ImageGenerationProviderError(safe_exception_summary(exc)) from exc


def generate_fabric_on_catalog_style(
    base_image_path: str,
    fabric_texture_path: str,
    mask_image_path: str | None,
    prompt: str,
) -> bytes:
    """Generate selected real fabric texture on a selected real catalog garment style."""

    return _edit_images([base_image_path, fabric_texture_path], prompt, mask_image_path=mask_image_path)


def generate_fabric_on_user_photo(user_photo_path: str, fabric_texture_path: str, prompt: str) -> bytes:
    """Generate selected fabric texture on a user's uploaded clothing photo."""

    return _edit_images([user_photo_path, fabric_texture_path], prompt)
