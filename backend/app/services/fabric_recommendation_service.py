"""Published fabric recommendation helpers.

The recommendation layer treats a fabric as an existing database row only.
Fabric photos come only from admin uploads. GPT may analyze a user request and
rank candidate fabric IDs, but it must never create or invent fabric records,
photos, prices, stock statuses, names, SKUs, or materials.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID

from app.config import get_settings

PREMIUM_TERMS = {"шелк", "шёлк", "атлас", "сатин", "жаккард", "купра", "вискоза", "премиум", "люкс"}
CALM_COLOR_TERMS = {"молоч", "айвори", "беж", "пудр", "нюд", "сер", "пастел", "крем", "бел"}
DRAPE_TERMS = {"драп", "струящ", "мягк", "пластич", "атлас", "шелк", "шёлк", "вискоза"}
LIGHT_TERMS = {"легк", "тонк", "дыша", "воздуш", "лет"}
TRANSPARENT_TERMS = {"прозрач", "просвеч"}
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

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


def _candidate_payload(fabric: Any) -> dict:
    return {
        "fabric_id": _fabric_id(fabric),
        "sku": getattr(fabric, "sku", None),
        "name": getattr(fabric, "name", None),
        "category": getattr(fabric, "category", None),
        "composition": getattr(fabric, "composition", None),
        "color": getattr(fabric, "color", None),
        "shade": getattr(fabric, "shade", None),
        "pattern": getattr(fabric, "pattern", None),
        "texture": getattr(fabric, "texture", None),
        "density": getattr(fabric, "density", None),
        "season": getattr(fabric, "season", None),
        "recommended_for": getattr(fabric, "recommended_for", None),
        "not_recommended_for": getattr(fabric, "not_recommended_for", None),
        "price_per_meter": str(getattr(fabric, "price_per_meter", "") or ""),
        "currency": getattr(fabric, "currency", None),
        "stock_status": getattr(fabric, "stock_status", None),
        "short_description": getattr(fabric, "short_description", None),
        "full_description": getattr(fabric, "full_description", None),
        "description_for_gpt": getattr(fabric, "description_for_gpt", None),
        "tags": getattr(fabric, "tags", None),
    }


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


def _parse_openai_ranked_items(content: str) -> list[dict]:
    parsed = json.loads(content)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        items = parsed.get("items") or parsed.get("recommendations") or []
        return items if isinstance(items, list) else []
    return []


def _rank_with_openai(preferences: dict, candidate_fabrics: list, limit: int) -> list[dict] | None:
    if not get_settings().is_openai_configured or not candidate_fabrics:
        return None

    fallback_by_id = {item["fabric_id"]: item for item in _fallback_rank(preferences, candidate_fabrics, len(candidate_fabrics))}
    candidate_payloads = [_candidate_payload(fabric) for fabric in candidate_fabrics]
    user_payload = {
        "preferences": preferences,
        "candidate_fabric_ids": [item["fabric_id"] for item in candidate_payloads],
        "candidate_fabrics": candidate_payloads,
        "return_json_shape": {
            "items": [
                {
                    "fabric_id": "candidate fabric_id only",
                    "score": 0.95,
                    "reason": "Почему эта реальная ткань подходит",
                    "possible_issue": "Что может не подойти или null",
                }
            ]
        },
    }
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": GPT_RANKING_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    request = Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {get_settings().openai_api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        raw_items = _parse_openai_ranked_items(response_data["choices"][0]["message"]["content"])
    except (KeyError, TypeError, ValueError, URLError, TimeoutError, OSError):
        return None

    sanitized = sanitize_ranked_fabric_ids(candidate_fabrics, raw_items)
    ranked: list[dict] = []
    for item in sanitized[:limit]:
        fabric_id = str(item.get("fabric_id"))
        fallback_item = fallback_by_id.get(fabric_id)
        if fallback_item is None:
            continue
        try:
            score = float(item.get("score", fallback_item["score"]))
        except (TypeError, ValueError):
            score = fallback_item["score"]
        ranked.append(
            {
                "fabric_id": fabric_id,
                "score": round(min(max(score, 0), 1), 2),
                "reason": str(item.get("reason") or fallback_item["reason"]),
                "possible_issue": item.get("possible_issue") or fallback_item.get("possible_issue"),
                "fabric": fallback_item["fabric"],
                "matched_fields": fallback_item.get("matched_fields", []),
            }
        )
    return ranked or None


def rank_fabrics_for_user(preferences: dict, candidate_fabrics: list, limit: int = 5) -> list[dict]:
    """Rank only real database fabrics passed as candidates.

    When OpenAI is configured, GPT ranks only the provided candidate IDs and the
    response is sanitized. Unknown IDs, malformed JSON, or API errors fall back
    to deterministic local scoring.
    """

    safe_limit = min(max(limit, 1), 5)
    openai_ranked = _rank_with_openai(preferences, candidate_fabrics, safe_limit)
    return openai_ranked or _fallback_rank(preferences, candidate_fabrics, safe_limit)


def build_fabric_recommendations(preferences: dict, candidate_fabrics: list, limit: int = 5) -> list[dict]:
    """Backward-compatible wrapper used by the public catalog route."""

    return rank_fabrics_for_user(preferences, candidate_fabrics, limit)
