"""Image generation integration isolated from API routes."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from app.config import get_settings

IMAGE_ERROR = "AI-визуализация пока недоступна: OpenAI API key не настроен."
IMAGE_EDIT_PROMPT = (
    "Replace only the fabric of the garment in the base image with the fabric texture from the reference image. "
    "Keep the exact silhouette, cut, seams, folds, pose, lighting, background and proportions. "
    "Preserve the garment construction and make the new fabric follow the folds naturally. "
    "Do not change the model's face, body, hair, background or accessories. "
    "Use the selected fabric realistically, including its color, pattern scale, texture and drape."
)


def _ensure_configured() -> str:
    settings = get_settings()
    if not settings.is_openai_configured:
        raise RuntimeError(IMAGE_ERROR)
    return settings.openai_api_key


def _open_file_tuple(path: str | Path):
    file_path = Path(path)
    return (file_path.name, file_path.open("rb"), "image/png")


def generate_fabric_on_catalog_style(base_image_path: str, fabric_texture_path: str, mask_image_path: str | None, prompt: str) -> bytes:
    """Generate selected real fabric texture on a selected real catalog garment style."""

    api_key = _ensure_configured()
    files = []
    try:
        files.append(("image[]", _open_file_tuple(base_image_path)))
        files.append(("image[]", _open_file_tuple(fabric_texture_path)))
        if mask_image_path:
            files.append(("mask", _open_file_tuple(mask_image_path)))
        data = {"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024"}
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://api.openai.com/v1/images/edits",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            )
            response.raise_for_status()
        payload = response.json()
        b64_json = payload.get("data", [{}])[0].get("b64_json")
        if not b64_json:
            raise RuntimeError("OpenAI не вернул изображение для визуализации.")
        return base64.b64decode(b64_json)
    finally:
        for _, file_tuple in files:
            file_tuple[1].close()


def generate_fabric_on_user_photo(user_photo_path, fabric_texture_path, prompt: str) -> bytes:
    _ensure_configured()
    return b""
