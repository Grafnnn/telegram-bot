from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from ..api_client import BackendApiClient
from ..keyboards import SELECTED_TEXT, main_menu_keyboard
from .common import send_fabric_card

router = Router()


@router.message(Command("selected"))
@router.message(F.text == SELECTED_TEXT)
async def selected_command(message: Message, api_client: BackendApiClient, backend_public_url: str) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.", reply_markup=main_menu_keyboard())
        return

    result = await api_client.get_selected_fabric(message.from_user.id)
    if not result.ok:
        await message.answer("Выбранная ткань временно недоступна. Попробуйте чуть позже.", reply_markup=main_menu_keyboard())
        return

    payload = result.data or {}
    fabric = payload.get("fabric")
    if not payload.get("selected") or fabric is None:
        await message.answer("Вы пока не выбрали ткань.", reply_markup=main_menu_keyboard())
        return

    await send_fabric_card(message, fabric, backend_public_url)
