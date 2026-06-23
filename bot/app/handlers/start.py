"""Start and help handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.handlers.fabric_selection import upsert_message_user
from app.keyboards import main_menu

router = Router()

WELCOME = "👗 Добро пожаловать!\n\nВы можете:"
HELP_TEXT = "Команды: /start, /catalog, /pick, /styles, /selected, /help"

@router.message(Command("start"))
async def start(message: Message) -> None:
    await upsert_message_user(message)
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(Command("help"))
@router.message(lambda message: message.text == "Помощь")
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())
