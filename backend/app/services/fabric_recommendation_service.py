"""Published fabric recommendation helpers.

The recommendation layer never creates fabrics and never returns IDs outside the
candidate list it receives from the database.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

PREMIUM_TERMS = {"шелк", "шёлк", "атлас", "сатин", "жаккард", "купра", "вискоза", "премиум", "люкс"}
CALM_COLOR_TERMS = {"молоч", "айвори", "беж", "пудр", "нюд", "сер", "пастел", "крем", "бел"}
DRAPE_TERMS = {"драп", "струящ", "мягк", "пластич", "атлас", "шелк", "шёлк", "вискоза"}
LIGHT_TERMS = {"легк", "тонк", "дыша", "воздуш", "лет"}
TRANSPARENT_TERMS = {"прозрач", "просвеч"}

GPT_RANKING_SYSTEM_PROMPT = (
    "Ты консультант по тканям. Твоя задача — выбрать подходящие ткани только из переданного списка. "
    "Нельзя придумывать новые ткани. Нельзя менять цены, названия, наличие и характеристики. "
    "Верни только fabric_id из списка candidate_fabric_ids и JSON с reason и possible_issue."
)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).lower() for item in value if item]
    return [str(value).lower()]


def _fabric_id(fabric: Any) -> str:
    return str(getattr(fabric, "id"))


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
    chunks.extend(_as_list(getattr(fabric, "not_recommended_for", None)))
    chunks.extend(_as_list(getattr(fabric, "tags", None)))
    return " ".join(chunks).lower()


def _has_term(text: str, terms: set[str] | list[str]) -> bool:
    return any(term in text for term in terms)


def _normalize_score(raw_score: int) -> float:
    return round(min(max(raw_score, 0), 20) / 20, 2)


def _score_and_explain(preferences: dict, fabric: Any) -> tuple[int, str, str | None, list[str]]:
    text = _text_for_fabric(fabric)
    score = 0
    reasons: list[str] = []
    possible_issues: list[str] = []
    matched_fields: list[str] = []

    garment_type = preferences.get("garment_type")
    recommended_for = _as_list(getattr(fabric, "recommended_for", None))
    if garment_type and (garment_type.lower() in " ".join(recommended_for) or garment_type.lower() in text):
        score += 5
        matched_fields.append("recommended_for")
        reasons.append(f"подходит для запроса: {garment_type}")

    season = preferences.get("season")
    seasons = _as_list(getattr(fabric, "season", None))
    if season and (season.lower() in seasons or season.lower() in text):
        score += 4
        matched_fields.append("season")
        reasons.append(f"соответствует сезону: {season}")

    occasion = preferences.get("occasion")
    if occasion and occasion.lower() in text:
        score += 3
        matched_fields.append("occasion")
        reasons.append(f"в карточке есть совпадение по поводу: {occasion}")

    desired_style = _as_list(preferences.get("desired_style"))
    if desired_style and _has_term(text, PREMIUM_TERMS):
        score += 3
        matched_fields.append("desired_style")
        reasons.append("материал выглядит уместно для дорогого и элегантного образа")

    preferred_colors = _as_list(preferences.get("preferred_colors"))
    if preferred_colors and any(color in text for color in preferred_colors):
        score += 3
        matched_fields.append("preferred_colors")
        reasons.append("цвет или оттенок совпадает с предпочтениями")

    avoid = _as_list(preferences.get("avoid"))
    if any("яр" in item for item in avoid):
        if _has_term(text, CALM_COLOR_TERMS):
            score += 3
            matched_fields.append("avoid")
            reasons.append("палитра выглядит спокойной и не слишком яркой")
        elif "яр" in text:
            score -= 3
            possible_issues.append("оттенок может быть ярче, чем нужно пользователю")
    if any("прозрач" in item for item in avoid) and _has_term(text, TRANSPARENT_TERMS):
        score -= 3
        possible_issues.append("ткань может быть слишком прозрачной")

    required_properties = _as_list(preferences.get("required_properties"))
    if any("драп" in item for item in required_properties) and _has_term(text, DRAPE_TERMS):
        score += 3
        matched_fields.append("required_properties")
        reasons.append("по описанию подходит для красивой драпировки")
    if any("комфорт" in item or "лег" in item for item in required_properties) and _has_term(text, LIGHT_TERMS):
        score += 2
        matched_fields.append("required_properties")
        reasons.append("есть признаки легкой и комфортной ткани")

    keywords = _as_list(preferences.get("keywords"))
    matched_keywords = [word for word in keywords if word in text]
    if matched_keywords:
        score += min(len(matched_keywords), 5)
        matched_fields.append("keywords")
        reasons.append("совпали ключевые слова: " + ", ".join(matched_keywords[:5]))

    stock_status = getattr(fabric, "stock_status", None)
    if stock_status == "in_stock":
        score += 2
    elif stock_status == "preorder":
        score += 1
    elif stock_status == "out_of_stock":
        score -= 5
        possible_issues.append("сейчас нет в наличии")

    price = getattr(fabric, "price_per_meter", None)
    if isinstance(price, Decimal) and price > 0:
        score += 1

    not_recommended = " ".join(_as_list(getattr(fabric, "not_recommended_for", None)))
    if garment_type and garment_type.lower() in not_recommended:
        score -= 5
        possible_issues.append(f"в карточке есть ограничение: не рекомендуется для {garment_type}")

    if not reasons:
        reasons.append("это ближайший опубликованный вариант из каталога по доступным характеристикам")

    return score, "; ".join(reasons), "; ".join(possible_issues) or None, matched_fields


def _fallback_rank(preferences: dict, candidate_fabrics: list, limit: int) -> list[dict]:
    ranked = []
    for fabric in candidate_fabrics:
        raw_score, reason, possible_issue, matched_fields = _score_and_explain(preferences, fabric)
        ranked.append(
            {
                "fabric_id": _fabric_id(fabric),
                "score": _normalize_score(raw_score),
                "reason": reason,
                "possible_issue": possible_issue,
                "fabric": fabric,
                "matched_fields": matched_fields,
            }
        )
    stock_order = {"in_stock": 2, "preorder": 1, "out_of_stock": 0}
    ranked.sort(
        key=lambda item: (
            item["score"],
            stock_order.get(getattr(item["fabric"], "stock_status", "out_of_stock"), 0),
            getattr(item["fabric"], "created_at", None),
        ),
        reverse=True,
    )
    return ranked[:limit]


def sanitize_ranked_fabric_ids(candidate_fabrics: list, ranked_items: list[dict]) -> list[dict]:
    """Drop GPT items that reference unknown fabric IDs."""

    allowed_ids = {_fabric_id(fabric) for fabric in candidate_fabrics}
    return [item for item in ranked_items if str(item.get("fabric_id")) in allowed_ids]


def rank_fabrics_for_user(preferences: dict, candidate_fabrics: list, limit: int = 5) -> list[dict]:
    """Rank only real database fabrics passed as candidates.

    A future GPT implementation must pass its JSON through
    `sanitize_ranked_fabric_ids` before returning. The current implementation is
    deterministic fallback scoring and therefore cannot invent fabric IDs.
    """

    safe_limit = min(max(limit, 1), 5)
    return _fallback_rank(preferences, candidate_fabrics, safe_limit)


def build_fabric_recommendations(preferences: dict, candidate_fabrics: list, limit: int = 5) -> list[dict]:
    """Backward-compatible wrapper used by the public catalog route."""

    return rank_fabrics_for_user(preferences, candidate_fabrics, limit)
