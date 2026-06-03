"""Start and help handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards import main_menu

router = Router()

WELCOME = "👗 Добро пожаловать!\n\nВы можете:"


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer("Команды: /start, /catalog, /pick, /styles, /help", reply_markup=main_menu())
