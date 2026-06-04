"""Generation handlers placeholder."""

from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message(lambda message: message.text == "Мои результаты")
async def generations(message: Message) -> None:
    await message.answer("История результатов будет подключена на следующем шаге MVP.")
