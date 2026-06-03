"""AI pick handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api_client import BackendAPIClient
from app.config import get_settings
from app.states import PickFabricStates

router = Router()


@router.message(Command("pick"))
@router.message(lambda message: message.text == "Подобрать ткань по описанию")
async def ask_description(message: Message, state: FSMContext) -> None:
    await state.set_state(PickFabricStates.waiting_for_description)
    await message.answer("Опишите, какую ткань вы ищете: цвет, сезон, изделие, фактуру.")


@router.message(PickFabricStates.waiting_for_description)
async def recommend(message: Message, state: FSMContext) -> None:
    fabrics = await BackendAPIClient(get_settings().backend_api_url).recommend_fabrics(message.text or "")
    await state.clear()
    if not fabrics:
        await message.answer("Не нашла подходящих опубликованных тканей. Попробуйте изменить описание.")
        return
    lines = ["Подходящие ткани:"]
    for fabric in fabrics:
        lines.append(f"• {fabric.get('name')} ({fabric.get('sku')})")
    await message.answer("\n".join(lines))
