from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urljoin

from aiogram.types import InlineKeyboardMarkup, Message


def get_main_image(fabric: dict[str, Any], backend_public_url: str) -> str | None:
    images = fabric.get("images") or []
    main_image = next((image for image in images if image.get("is_main")), images[0] if images else None)
    if not main_image or not main_image.get("image_url"):
        return None
    image_url = main_image["image_url"]
    if image_url.startswith("/uploads"):
        return urljoin(backend_public_url.rstrip("/") + "/", image_url.lstrip("/"))
    return image_url


def format_fabric_card(fabric: dict[str, Any]) -> str:
    return "\n".join(
        part
        for part in [
            f"<b>{escape(str(fabric.get('name') or 'Ткань'))}</b>",
            f"Категория: {escape(str(fabric.get('category')))}" if fabric.get("category") else None,
            f"Цвет: {escape(str(fabric.get('color')))}" if fabric.get("color") else None,
            f"Цена: {escape(str(fabric.get('price')))}" if fabric.get("price") else None,
            f"Наличие: {escape(str(fabric.get('availability')))}" if fabric.get("availability") else None,
            escape(str(fabric.get("short_description"))) if fabric.get("short_description") else None,
        ]
        if part
    )


def format_recommendation_card(recommendation: dict[str, Any]) -> str:
    fabric = recommendation.get("fabric") or {}
    base = [
        f"<b>{escape(str(fabric.get('name') or 'Ткань'))}</b>",
        f"Цена: {escape(str(fabric.get('price')))}" if fabric.get("price") else None,
        f"Наличие: {escape(str(fabric.get('availability')))}" if fabric.get("availability") else None,
        f"Почему подходит: {escape(str(recommendation.get('why')))}" if recommendation.get("why") else None,
        f"Возможный минус: {escape(str(recommendation.get('possible_minus')))}"
        if recommendation.get("possible_minus")
        else None,
    ]
    return "\n".join(part for part in base if part)


async def send_fabric_card(
    message: Message,
    fabric: dict[str, Any],
    backend_public_url: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    caption: str | None = None,
) -> None:
    text = caption or format_fabric_card(fabric)
    image_url = get_main_image(fabric, backend_public_url)
    if image_url:
        try:
            await message.answer_photo(image_url, caption=text, reply_markup=reply_markup, parse_mode="HTML")
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
