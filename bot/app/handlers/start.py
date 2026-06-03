from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..api_client import BackendApiClient
from ..keyboards import CATALOG_TEXT, HELP_TEXT, PICK_TEXT, SELECTED_TEXT, main_menu_keyboard

router = Router()

WELCOME_TEXT = """👗 Добро пожаловать!

Вы можете:
• Выбрать ткань из каталога
• Подобрать ткань по описанию
• Посмотреть мою выбранную ткань
• Получить помощь"""

HELP_MESSAGE = """Я помогаю выбрать ткань только из опубликованного каталога.

Команды:
/catalog — открыть каталог тканей
/pick — подобрать ткань по описанию
/selected — показать выбранную ткань
/help — помощь

GPT не создает и не загружает ткани: он только помогает выбрать среди опубликованных тканей из базы."""


async def upsert_from_message(message: Message, api_client: BackendApiClient) -> None:
    user = message.from_user
    if user is None:
        return
    await api_client.upsert_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )


@router.message(Command("start"))
async def start_command(message: Message, api_client: BackendApiClient) -> None:
    await upsert_from_message(message, api_client)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
@router.message(lambda message: message.text == HELP_TEXT)
async def help_command(message: Message) -> None:
    await message.answer(HELP_MESSAGE, reply_markup=main_menu_keyboard())
