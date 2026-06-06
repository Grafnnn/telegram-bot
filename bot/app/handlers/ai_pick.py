"""AI pick handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api_client import BackendAPIClient
from app.config import get_settings
from app.handler_utils import friendly_api_error_message
from app.handlers.fabric_selection import answer_fabric_card, upsert_message_user
from app.states import PickFabricStates

router = Router()


@router.message(Command("pick"))
@router.message(lambda message: message.text == "Подобрать ткань по описанию")
async def ask_description(message: Message, state: FSMContext) -> None:
    await upsert_message_user(message)
    await state.set_state(PickFabricStates.waiting_for_description)
    await message.answer("Опишите, для какой вещи и случая нужна ткань. Например: летнее платье на свадьбу, пастельный цвет, чтобы выглядело дорого.")


@router.message(PickFabricStates.waiting_for_description)
async def recommend(message: Message, state: FSMContext) -> None:
    try:
        recommendations = await BackendAPIClient(get_settings().backend_api_url).recommend_fabrics(message.text or "")
    except Exception as exc:
        await state.clear()
        await message.answer(friendly_api_error_message(exc))
        return
    await state.clear()
    if not recommendations:
        await message.answer("Пока в каталоге нет опубликованных тканей для подбора.")
        return
    await message.answer("Подобрала реальные ткани из опубликованного каталога:")
    for item in recommendations[:5]:
        fabric = item.get("fabric", item)
        reason = item.get("reason") or "Подходит по характеристикам из каталога."
        possible_issue = item.get("possible_issue")
        await answer_fabric_card(message, fabric, reason=reason, possible_issue=possible_issue, source="pick")
