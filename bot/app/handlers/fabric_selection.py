"""Shared fabric selection helpers and callback handlers."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.api_client import BackendAPIClient
from app.config import get_settings
from app.handler_utils import friendly_api_error_message, parse_callback_uuid
from app.keyboards import select_fabric_keyboard
from app.redaction import safe_exception_summary

router = Router()
logger = logging.getLogger(__name__)

STOCK_LABELS = {"in_stock": "В наличии", "preorder": "Под заказ", "out_of_stock": "Нет в наличии"}


def backend_client() -> BackendAPIClient:
    return BackendAPIClient(get_settings().backend_api_url)


def fabric_image_url(fabric: dict[str, Any]) -> str | None:
    images = fabric.get("images") or []
    main_image = next((image for image in images if image.get("image_type") == "main"), None) or (images[0] if images else None)
    if not main_image:
        return None
    image_url = main_image.get("image_url")
    if not image_url:
        return None
    if image_url.startswith("/uploads"):
        return f"{get_settings().backend_public_url.rstrip('/')}{image_url}"
    return image_url


def format_fabric_card(fabric: dict[str, Any], reason: str | None = None, possible_issue: str | None = None) -> str:
    price = fabric.get("price_per_meter") or "цена не указана"
    currency = fabric.get("currency") or "RUB"
    stock_status = STOCK_LABELS.get(str(fabric.get("stock_status")), str(fabric.get("stock_status") or "—"))
    lines = [
        f"{fabric.get('name')} ({fabric.get('sku')})",
        f"Категория: {fabric.get('category') or '—'}",
        f"Цена: {price} {currency} / м",
        f"Наличие: {stock_status}",
    ]
    if fabric.get("short_description"):
        lines.append(str(fabric["short_description"]))
    if reason:
        lines.append(f"Почему подходит: {reason}")
    if possible_issue:
        lines.append(f"Возможный минус: {possible_issue}")
    return "\n".join(lines)


async def answer_fabric_card(message: Message, fabric: dict[str, Any], reason: str | None = None, possible_issue: str | None = None, source: str = "fabric") -> None:
    text = format_fabric_card(fabric, reason, possible_issue)
    keyboard = select_fabric_keyboard(str(fabric.get("id")), source)
    image_url = fabric_image_url(fabric)
    if image_url:
        try:
            await message.answer_photo(image_url, caption=text, reply_markup=keyboard)
            return
        except Exception as exc:
            logger.warning("Could not send fabric image: %s", safe_exception_summary(exc))
    await message.answer(text, reply_markup=keyboard)


async def upsert_message_user(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        await backend_client().upsert_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    except Exception as exc:
        logger.warning("Could not sync Telegram user before handling message: %s", exc.__class__.__name__)


@router.callback_query(lambda callback: bool(callback.data) and (callback.data.startswith("fabric:select:") or callback.data.startswith("pick:select:")))
async def select_fabric_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return
    fabric_id = parse_callback_uuid(callback.data, "fabric:select:") or parse_callback_uuid(callback.data, "pick:select:")
    if fabric_id is None:
        await callback.answer("Эта кнопка больше не актуальна. Откройте каталог заново.", show_alert=True)
        return
    try:
        await backend_client().upsert_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        await backend_client().select_fabric(callback.from_user.id, fabric_id)
    except Exception as exc:
        await callback.answer(friendly_api_error_message(exc), show_alert=True)
        return
    await callback.answer("Ткань выбрана.", show_alert=False)
    if callback.message:
        await callback.message.answer("Ткань выбрана. Посмотреть выбор можно командой /selected.")
