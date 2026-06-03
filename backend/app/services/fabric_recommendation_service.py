"""Published fabric recommendation helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

PREMIUM_TERMS = {"шелк", "шёлк", "атлас", "сатин", "жаккард", "купра", "вискоза", "премиум", "люкс"}
CALM_COLOR_TERMS = {"молоч", "айвори", "беж", "пудр", "нюд", "сер", "пастел", "крем", "бел"}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).lower() for item in value if item]
    return [str(value).lower()]


def _text_for_fabric(fabric: Any) -> str:
    fields = [
        "sku",
        "name",
        "category",
        "composition",
        "color",
        "shade",
        "pattern",
        "texture",
        "density",
        "stretch",
        "opacity",
        "shine",
        "short_description",
        "full_description",
        "description_for_gpt",
    ]
    chunks = [str(getattr(fabric, field, "") or "") for field in fields]
    chunks.extend(_as_list(getattr(fabric, "season", None)))
    chunks.extend(_as_list(getattr(fabric, "recommended_for", None)))
    chunks.extend(_as_list(getattr(fabric, "tags", None)))
    return " ".join(chunks).lower()


def _has_term(text: str, terms: set[str] | list[str]) -> bool:
    return any(term in text for term in terms)


def _score_and_explain(preferences: dict, fabric: Any) -> tuple[int, list[str], list[str]]:
    text = _text_for_fabric(fabric)
    score = 0
    explanations: list[str] = []
    matched_fields: list[str] = []

    garment_type = preferences.get("garment_type")
    recommended_for = _as_list(getattr(fabric, "recommended_for", None))
    if garment_type and (garment_type.lower() in " ".join(recommended_for) or garment_type.lower() in text):
        score += 5
        matched_fields.append("recommended_for")
        explanations.append(f"подходит для изделия: {garment_type}")

    season = preferences.get("season")
    seasons = _as_list(getattr(fabric, "season", None))
    if season and (season.lower() in seasons or season.lower() in text):
        score += 4
        matched_fields.append("season")
        explanations.append(f"соответствует сезону: {season}")

    occasion = preferences.get("occasion")
    if occasion and occasion.lower() in text:
        score += 3
        matched_fields.append("occasion")
        explanations.append(f"в описании есть совпадение по поводу: {occasion}")

    desired_style = preferences.get("desired_style")
    if desired_style and _has_term(text, PREMIUM_TERMS):
        score += 3
        matched_fields.append("style")
        explanations.append("материал выглядит уместно для дорогого и элегантного образа")

    colors = preferences.get("colors") or []
    if colors and any(str(color).lower() in text for color in colors):
        score += 2
        matched_fields.append("color")
        explanations.append("цвет или оттенок совпадает с запросом")

    constraints = preferences.get("constraints") or []
    if "не ярко" in constraints and _has_term(text, CALM_COLOR_TERMS):
        score += 3
        matched_fields.append("constraints")
        explanations.append("палитра выглядит спокойной и не слишком яркой")

    keywords = preferences.get("keywords") or []
    matched_keywords = [str(word).lower() for word in keywords if str(word).lower() in text]
    if matched_keywords:
        score += min(len(matched_keywords), 5)
        matched_fields.append("keywords")
        explanations.append("совпали ключевые слова: " + ", ".join(matched_keywords[:5]))

    price = getattr(fabric, "price_per_meter", None)
    if isinstance(price, Decimal) and price > 0:
        score += 1

    not_recommended = " ".join(_as_list(getattr(fabric, "not_recommended_for", None)))
    if garment_type and garment_type.lower() in not_recommended:
        score -= 5
        explanations.append(f"есть ограничение: не рекомендуется для {garment_type}")

    if not explanations:
        explanations.append("это ближайший опубликованный вариант из каталога")

    return score, explanations, matched_fields


def build_fabric_recommendations(preferences: dict, candidate_fabrics: list, limit: int = 3) -> list[dict]:
    """Return ranked real fabrics from the database with human-readable explanations."""

    ranked = []
    for fabric in candidate_fabrics:
        score, explanations, matched_fields = _score_and_explain(preferences, fabric)
        ranked.append(
            {
                "fabric": fabric,
                "score": score,
                "explanation": "; ".join(explanations),
                "matched_fields": matched_fields,
            }
        )
    ranked.sort(key=lambda item: (item["score"], getattr(item["fabric"], "created_at", None)), reverse=True)
    return ranked[:limit]


def rank_fabrics_for_user(preferences: dict, candidate_fabrics: list) -> list:
    """Backward-compatible helper that returns fabrics only."""

    return [item["fabric"] for item in build_fabric_recommendations(preferences, candidate_fabrics, len(candidate_fabrics))]
