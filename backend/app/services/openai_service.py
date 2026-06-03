"""OpenAI service stubs with clear configuration errors."""

from app.config import get_settings

OPENAI_ERROR = "OPENAI_API_KEY не настроен. Скопируйте .env.example в .env и замените put_openai_key_here."

FIELD_LABELS = {
    "sku": "артикул",
    "name": "название",
    "category": "категория",
    "price_per_meter": "цена за метр",
    "stock_status": "наличие",
    "main image": "главное фото",
    "texture image": "фото фактуры",
    "description_for_gpt": "описание для GPT",
}


def _not_configured() -> dict:
    return {"ok": False, "error": OPENAI_ERROR}


def extract_fabric_preferences(user_text: str) -> dict:
    if not get_settings().is_openai_configured:
        return {**_not_configured(), "preferences": {"query": user_text}}
    return {"ok": True, "preferences": {"query": user_text}}


def generate_admin_fabric_description(fabric_data: dict, image_url: str | None = None) -> dict:
    if not get_settings().is_openai_configured:
        return _not_configured()
    name = fabric_data.get("name") or "ткань"
    category = fabric_data.get("category") or "ткань"
    color = fabric_data.get("color") or "актуальный оттенок"
    return {
        "ok": True,
        "short_description": f"{name}: {color} {category} для стильных изделий.",
        "full_description": f"{name} — материал категории «{category}» с выразительной фактурой. Подойдет для продуманных капсульных образов и аккуратного пошива.",
        "description_for_gpt": f"Материал: {name}. Категория: {category}. Цвет: {color}. Учитывать состав, фактуру, сезонность и назначение при подборе изделия.",
        "tags": [tag for tag in [category, color, fabric_data.get("pattern")] if tag],
        "recommended_for": fabric_data.get("recommended_for") or [],
        "not_recommended_for": fabric_data.get("not_recommended_for") or [],
        "image_url": image_url,
    }


def check_fabric_card(fabric_data: dict) -> dict:
    required = ["sku", "name", "category", "price_per_meter", "stock_status", "description_for_gpt"]
    missing = [field for field in required if not fabric_data.get(field)]
    images = fabric_data.get("images") or []
    image_types = {image.get("image_type") for image in images if isinstance(image, dict)}
    has_main = bool(fabric_data.get("has_main_image")) or "main" in image_types
    has_texture = bool(fabric_data.get("has_texture_image")) or "texture" in image_types
    if not has_main:
        missing.append("main image")
    if not has_texture:
        missing.append("texture image")
    recommendations = [f"Заполните поле или добавьте: {FIELD_LABELS.get(field, field)}" for field in missing]
    is_ready = not missing
    return {
        "ok": is_ready,
        "is_ready": is_ready,
        "missing_fields": missing,
        "recommendations": recommendations,
        "message": "Карточка готова к публикации." if is_ready else "Заполните обязательные поля перед публикацией.",
    }
