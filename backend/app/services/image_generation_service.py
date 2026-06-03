"""Image generation stubs."""

from app.config import get_settings

IMAGE_ERROR = "OPENAI_API_KEY не настроен; генерация изображений пока недоступна."


def _ensure_configured() -> None:
    if not get_settings().is_openai_configured:
        raise RuntimeError(IMAGE_ERROR)


def generate_fabric_on_catalog_style(base_image_path, fabric_texture_path, mask_image_path: object | None, prompt: str) -> bytes:
    _ensure_configured()
    return b""


def generate_fabric_on_user_photo(user_photo_path, fabric_texture_path, prompt: str) -> bytes:
    _ensure_configured()
    return b""
