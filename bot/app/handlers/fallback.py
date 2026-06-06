"""Fallback handlers for stale or unknown bot callbacks."""

from aiogram import Router
from aiogram.types import CallbackQuery

from app.handler_utils import UNKNOWN_CALLBACK_MESSAGE

router = Router()


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer(UNKNOWN_CALLBACK_MESSAGE, show_alert=True)
