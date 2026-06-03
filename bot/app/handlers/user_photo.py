"""User photo handlers placeholder."""

from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message(lambda message: message.text == "Загрузить свое фото")
async def user_photo(message: Message) -> None:
    await message.answer("Загрузка фото будет подключена на следующем шаге MVP.")
