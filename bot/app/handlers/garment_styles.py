"""Garment style handlers."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import BackendAPIClient
from app.config import get_settings
from app.handlers.fabric_selection import upsert_message_user

router = Router()
logger = logging.getLogger(__name__)


def backend_client() -> BackendAPIClient:
    return BackendAPIClient(get_settings().backend_api_url)


def style_image_url(style: dict[str, Any]) -> str | None:
    image_url = style.get("base_image_url")
    if not image_url:
        return None
    if image_url.startswith("/uploads"):
        return f"{get_settings().backend_public_url.rstrip('/')}{image_url}"
    return image_url


def format_style_card(style: dict[str, Any]) -> str:
    lines = [f"{style.get('name')} — {style.get('category')}"]
    if style.get("description"):
        lines.append(str(style["description"]))
    compatible = style.get("compatible_fabric_categories") or []
    if compatible:
        lines.append(f"Подходит для тканей: {', '.join(compatible)}")
    return "\n".join(lines)


def select_style_keyboard(style_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Выбрать этот фасон", callback_data=f"style:select:{style_id}")]])


async def answer_style_card(message: Message, style: dict[str, Any]) -> None:
    text = format_style_card(style)
    keyboard = select_style_keyboard(str(style.get("id")))
    image_url = style_image_url(style)
    if image_url:
        try:
            await message.answer_photo(image_url, caption=text, reply_markup=keyboard)
            return
        except Exception as exc:
            logger.warning("Could not send garment style image %s: %s", image_url, exc)
    await message.answer(text, reply_markup=keyboard)


async def show_styles(message: Message) -> None:
    await upsert_message_user(message)
    styles = await backend_client().get_garment_styles()
    if not styles:
        await message.answer("Пока нет опубликованных фасонов.")
        return
    await message.answer("Опубликованные фасоны:")
    for style in styles[:10]:
        await answer_style_card(message, style)


@router.message(Command("styles"))
async def styles_command(message: Message) -> None:
    await show_styles(message)


@router.message(lambda message: message.text == "Выбрать фасон")
async def styles_button(message: Message) -> None:
    await show_styles(message)


@router.callback_query(lambda callback: bool(callback.data) and callback.data.startswith("style:select:"))
async def select_style_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return
    style_id = callback.data.split(":", 2)[2]
    await backend_client().upsert_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )
    result = await backend_client().select_garment_style(callback.from_user.id, style_id)
    if result is None:
        await callback.answer("Не удалось выбрать фасон. Возможно, он больше не опубликован.", show_alert=True)
        return
    await callback.answer("Фасон выбран.", show_alert=False)
    if callback.message:
        await callback.message.answer("Фасон выбран. Посмотреть текущий выбор можно командой /selected.")
