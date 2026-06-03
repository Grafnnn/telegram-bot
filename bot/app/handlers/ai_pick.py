"""AI pick handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api_client import BackendAPIClient
from app.config import get_settings
from app.keyboards import pick_fabric_keyboard
from app.states import PickFabricStates

router = Router()


@router.message(Command("pick"))
@router.message(lambda message: message.text == "Подобрать ткань по описанию")
async def ask_description(message: Message, state: FSMContext) -> None:
    await state.set_state(PickFabricStates.waiting_for_description)
    await message.answer("Опишите, для какой вещи и случая нужна ткань. Например: летнее платье на свадьбу, пастельный цвет, чтобы выглядело дорого.")


@router.message(PickFabricStates.waiting_for_description)
async def recommend(message: Message, state: FSMContext) -> None:
    fabrics = await BackendAPIClient(get_settings().backend_api_url).recommend_fabrics(message.text or "")
    await state.clear()
    if not fabrics:
        await message.answer("Пока в каталоге нет опубликованных тканей для подбора.")
        return
    for item in fabrics[:5]:
        fabric = item.get("fabric", item)
        reason = item.get("reason") or item.get("explanation") or "Подходит по характеристикам из каталога."
        possible_issue = item.get("possible_issue")
        price = fabric.get("price_per_meter") or "цена не указана"
        currency = fabric.get("currency") or "RUB"
        stock_status = fabric.get("stock_status") or "unknown"
        text = (
            f"{fabric.get('name')} ({fabric.get('sku')})\n"
            f"Цена: {price} {currency} / м\n"
            f"Наличие: {stock_status}\n"
            f"Почему подходит: {reason}"
        )
        if possible_issue:
            text += f"\nВозможный минус: {possible_issue}"
        await message.answer(text, reply_markup=pick_fabric_keyboard(str(item.get("fabric_id") or fabric.get("id"))))
