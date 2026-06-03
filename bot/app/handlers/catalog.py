"""Catalog handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import BackendAPIClient
from app.config import get_settings

router = Router()


async def show_catalog(message: Message) -> None:
    fabrics = await BackendAPIClient(get_settings().backend_api_url).get_fabrics()
    if not fabrics:
        await message.answer("Пока нет опубликованных тканей.")
        return
    lines = ["Опубликованные ткани:"]
    for fabric in fabrics[:10]:
        price = fabric.get("price_per_meter") or "—"
        lines.append(f"• {fabric.get('name')} ({fabric.get('sku')}) — {price} {fabric.get('currency', 'RUB')}")
    await message.answer("\n".join(lines))


@router.message(Command("catalog"))
async def catalog_command(message: Message) -> None:
    await show_catalog(message)


@router.message(lambda message: message.text == "Выбрать ткань из каталога")
async def catalog_button(message: Message) -> None:
    await show_catalog(message)
