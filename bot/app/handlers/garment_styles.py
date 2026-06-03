"""Garment style handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import BackendAPIClient
from app.config import get_settings

router = Router()


async def show_styles(message: Message) -> None:
    styles = await BackendAPIClient(get_settings().backend_api_url).get_garment_styles()
    if not styles:
        await message.answer("Пока нет опубликованных фасонов.")
        return
    lines = ["Опубликованные фасоны:"]
    for style in styles[:10]:
        lines.append(f"• {style.get('name')} — {style.get('category')}")
    await message.answer("\n".join(lines))


@router.message(Command("styles"))
async def styles_command(message: Message) -> None:
    await show_styles(message)


@router.message(lambda message: message.text == "Выбрать фасон")
async def styles_button(message: Message) -> None:
    await show_styles(message)
