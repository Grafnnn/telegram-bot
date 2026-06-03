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


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _local_extract_fabric_preferences(user_text: str) -> dict:
    """Extract recommendation signals locally until the real GPT integration is added."""

    text = user_text.lower()
    garment_type = None
    if _contains_any(text, ["плать", "сарафан"]):
        garment_type = "платье"
    elif _contains_any(text, ["костюм", "жакет", "пиджак"]):
        garment_type = "костюм"
    elif _contains_any(text, ["юбк"]):
        garment_type = "юбка"
    elif _contains_any(text, ["рубаш", "блуз"]):
        garment_type = "блуза"

    occasion = None
    if _contains_any(text, ["свадьб", "венчани"]):
        occasion = "свадьба"
    elif _contains_any(text, ["вечер", "праздник", "торжеств"]):
        occasion = "вечернее мероприятие"
    elif _contains_any(text, ["офис", "работ"]):
        occasion = "офис"

    season = None
    if _contains_any(text, ["лет", "жар", "тепл"]):
        season = "лето"
    elif _contains_any(text, ["зим", "холод"]):
        season = "зима"
    elif _contains_any(text, ["весн"]):
        season = "весна"
    elif _contains_any(text, ["осен"]):
        season = "осень"

    desired_style = None
    if _contains_any(text, ["дорог", "роскош", "элегант", "преми", "наряд"]):
        desired_style = "дорого и элегантно"
    elif _contains_any(text, ["повседнев", "базов"]):
        desired_style = "повседневно"

    color_words = [
        "бел",
        "молоч",
        "айвори",
        "беж",
        "пудр",
        "розов",
        "голуб",
        "син",
        "черн",
        "сер",
        "зелен",
        "красн",
        "ярк",
        "пастел",
    ]
    colors = [word for word in color_words if word in text]

    constraints = []
    if _contains_any(text, ["не яр", "неяр", "без яр", "спокойн", "сдержан"]):
        constraints.append("не ярко")
    if _contains_any(text, ["не мнется", "немнущ", "не мял"]):
        constraints.append("мало мнется")
    if _contains_any(text, ["дыша", "легк", "воздуш"]):
        constraints.append("легкая и дышащая")

    stop_words = {"мне", "нужна", "нужен", "ткань", "для", "чтобы", "выглядело", "но", "или", "под", "на"}
    keywords = [word.strip(".,!?;:()[]{}«»\"'") for word in text.split()]
    keywords = [word for word in keywords if len(word) > 2 and word not in stop_words]

    return {
        "query": user_text,
        "garment_type": garment_type,
        "occasion": occasion,
        "season": season,
        "desired_style": desired_style,
        "colors": colors,
        "constraints": constraints,
        "keywords": keywords,
    }


def extract_fabric_preferences(user_text: str) -> dict:
    preferences = _local_extract_fabric_preferences(user_text)
    if not get_settings().is_openai_configured:
        return {**_not_configured(), "preferences": preferences}
    return {"ok": True, "preferences": preferences}


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
