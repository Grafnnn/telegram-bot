"""OpenAI service stubs with clear configuration errors and safe fallbacks."""

from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings

OPENAI_ERROR = "OPENAI_API_KEY не настроен. Скопируйте .env.example в .env и замените put_openai_key_here."
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

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

PREFERENCE_SYSTEM_PROMPT = (
    "Ты консультант по тканям. Проанализируй запрос пользователя и верни только JSON с ключами: "
    "garment_type, occasion, desired_style, preferred_colors, avoid, season, required_properties. "
    "Не придумывай ткани, названия, артикулы, фото, цены, составы или карточки тканей. "
    "Твоя задача — только извлечь требования для последующего поиска существующих тканей в базе."
)


def _not_configured() -> dict:
    return {"ok": False, "error": OPENAI_ERROR}


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _clean_preferences(raw: dict) -> dict:
    def list_value(name: str) -> list[str]:
        value = raw.get(name)
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return [str(value)]

    def nullable_string(name: str) -> str | None:
        value = raw.get(name)
        return str(value) if value else None

    return {
        "garment_type": nullable_string("garment_type"),
        "occasion": nullable_string("occasion"),
        "desired_style": list_value("desired_style"),
        "preferred_colors": list_value("preferred_colors"),
        "avoid": list_value("avoid"),
        "season": nullable_string("season"),
        "required_properties": list_value("required_properties"),
    }


def _local_extract_fabric_preferences(user_text: str) -> dict:
    """Extract recommendation signals locally until the real GPT integration is available."""

    text = user_text.lower()

    garment_type = None
    if _contains_any(text, ["плать", "сарафан"]):
        garment_type = "летнее платье" if _contains_any(text, ["лет", "жар", "тепл"]) else "платье"
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

    desired_style: list[str] = []
    if _contains_any(text, ["дорог", "роскош", "преми", "люкс"]):
        desired_style.extend(["дорого", "элегантно"])
    if _contains_any(text, ["элегант", "наряд", "изыск"]) and "элегантно" not in desired_style:
        desired_style.append("элегантно")
    if _contains_any(text, ["не яр", "неяр", "без яр", "спокойн", "сдержан"]):
        desired_style.append("не слишком ярко")

    preferred_colors: list[str] = []
    color_map = {
        "пастел": "пастельный",
        "беж": "бежевый",
        "пудр": "пудровый",
        "молоч": "молочный",
        "айвори": "айвори",
        "бел": "белый",
        "розов": "розовый",
        "голуб": "голубой",
        "сер": "серый",
    }
    for marker, color in color_map.items():
        if marker in text and color not in preferred_colors:
            preferred_colors.append(color)
    if not preferred_colors and "не слишком ярко" in desired_style:
        preferred_colors.extend(["пастельный", "бежевый", "пудровый"])

    avoid: list[str] = []
    if _contains_any(text, ["не яр", "неяр", "без яр", "слишком яр"]):
        avoid.append("слишком яркий")
    if _contains_any(text, ["не прозрач", "не просвеч", "слишком прозрач"]):
        avoid.append("слишком прозрачный")

    required_properties: list[str] = []
    if _contains_any(text, ["комфорт", "удоб", "приятн"]):
        required_properties.append("комфорт")
    if _contains_any(text, ["драп", "струящ", "пластич"]):
        required_properties.append("красивая драпировка")
    if _contains_any(text, ["легк", "воздуш", "дыша", "лет"]):
        required_properties.append("легкость")
    if garment_type and "платье" in garment_type and "красивая драпировка" not in required_properties:
        required_properties.append("красивая драпировка")

    return _clean_preferences(
        {
            "garment_type": garment_type,
            "occasion": occasion,
            "desired_style": desired_style,
            "preferred_colors": preferred_colors,
            "avoid": avoid,
            "season": season,
            "required_properties": required_properties,
        }
    )


def _extract_preferences_with_openai(user_text: str) -> dict | None:
    settings = get_settings()
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PREFERENCE_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    }
    request = Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, TypeError, ValueError, URLError, TimeoutError, OSError):
        return None
    return _clean_preferences(parsed)


def extract_fabric_preferences(user_text: str) -> dict:
    fallback_preferences = _local_extract_fabric_preferences(user_text)
    if not get_settings().is_openai_configured:
        return {**_not_configured(), "preferences": fallback_preferences}
    preferences = _extract_preferences_with_openai(user_text)
    if preferences is None:
        return {"ok": False, "error": "OpenAI не вернул корректный JSON preferences; используется fallback.", "preferences": fallback_preferences}
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
