"""Start and help handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.handlers.fabric_selection import upsert_message_user
from app.keyboards import CHANGE_FABRIC_ON_PHOTO_TEXT, main_menu, try_on_disabled_keyboard

router = Router()

WELCOME = "👗 Добро пожаловать!\n\nВы можете:"
HELP_TEXT = "Команды: /start, /catalog, /pick, /styles, /selected, /help"
PHOTO_TRY_ON_UNAVAILABLE_TEXT = (
    "Поменять ткань на пользовательском фото пока нельзя: мы не будем запускать режим, "
    "который создает новое изображение вместо точного редактирования исходного фото.\n\n"
    "Каталог тканей, подбор по описанию и выбор фасона работают."
)


@router.message(Command("start"))
async def start(message: Message) -> None:
    await upsert_message_user(message)
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(lambda message: message.text == CHANGE_FABRIC_ON_PHOTO_TEXT)
async def change_fabric_on_photo(message: Message) -> None:
    await message.answer(PHOTO_TRY_ON_UNAVAILABLE_TEXT, reply_markup=try_on_disabled_keyboard())


@router.message(Command("help"))
@router.message(lambda message: message.text == "Помощь")
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())
