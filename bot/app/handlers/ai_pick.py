from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..api_client import BackendApiClient
from ..keyboards import PICK_TEXT, main_menu_keyboard, recommendation_keyboard
from ..states import PickFabricStates
from .common import format_recommendation_card, get_main_image

router = Router()
PROMPT = "Опишите, для какой вещи и случая нужна ткань. Например: летнее платье на свадьбу, пастельный цвет, чтобы выглядело дорого."


@router.message(Command("pick"))
@router.message(F.text == PICK_TEXT)
async def pick_command(message: Message, state: FSMContext) -> None:
    await state.set_state(PickFabricStates.waiting_for_description)
    await message.answer(PROMPT)


@router.message(PickFabricStates.waiting_for_description)
async def process_pick_description(
    message: Message,
    state: FSMContext,
    api_client: BackendApiClient,
    backend_public_url: str,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправьте описание текстом.")
        return

    await state.clear()
    result = await api_client.recommend_fabrics(text)
    if not result.ok:
        await message.answer("Подбор временно недоступен. Попробуйте выбрать ткань из каталога.", reply_markup=main_menu_keyboard())
        return

    recommendations_payload = result.data or []
    recommendations = (
        recommendations_payload.get("recommendations", [])
        if isinstance(recommendations_payload, dict)
        else recommendations_payload
    )
    if not recommendations:
        await message.answer(
            "Не нашлось подходящих тканей. Попробуйте изменить описание или выбрать ткань из каталога.",
            reply_markup=main_menu_keyboard(),
        )
        return

    for recommendation in recommendations[:5]:
        fabric = recommendation.get("fabric") or {}
        caption = format_recommendation_card(recommendation)
        image_url = get_main_image(fabric, backend_public_url)
        markup = recommendation_keyboard(fabric.get("id", ""))
        if image_url:
            try:
                await message.answer_photo(image_url, caption=caption, reply_markup=markup, parse_mode="HTML")
                continue
            except Exception:
                pass
        await message.answer(caption, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("pick:select:"))
async def select_recommended_fabric(callback: CallbackQuery, api_client: BackendApiClient) -> None:
    fabric_id = (callback.data or "").split(":", maxsplit=2)[-1]
    result = await api_client.select_fabric(callback.from_user.id, fabric_id)
    if not result.ok:
        await callback.answer("Не удалось выбрать ткань. Попробуйте другую.", show_alert=True)
        return
    fabric = (result.data or {}).get("fabric") or {}
    name = fabric.get("name") or "ткань"
    if callback.message:
        await callback.message.answer(f"Ткань выбрана: {name}. Теперь можно перейти к выбору фасона.")
    await callback.answer("Ткань выбрана")
