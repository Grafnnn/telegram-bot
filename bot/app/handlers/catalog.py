"""Catalog handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import BackendAPIClient
from app.config import get_settings
from app.handler_utils import friendly_api_error_message
from app.handlers.fabric_selection import answer_fabric_card, upsert_message_user

router = Router()


async def show_catalog(message: Message) -> None:
    await upsert_message_user(message)
    try:
        fabrics = await BackendAPIClient(get_settings().backend_api_url).get_fabrics(limit=10)
    except Exception as exc:
        await message.answer(friendly_api_error_message(exc))
        return
    if not fabrics:
        await message.answer("Пока нет опубликованных тканей.")
        return
    await message.answer("Опубликованные ткани:")
    for fabric in fabrics[:10]:
        await answer_fabric_card(message, fabric, source="fabric")


@router.message(Command("catalog"))
async def catalog_command(message: Message) -> None:
    await show_catalog(message)


@router.message(lambda message: message.text == "Выбрать ткань из каталога")
async def catalog_button(message: Message) -> None:
    await show_catalog(message)
