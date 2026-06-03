from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..api_client import BackendApiClient
from ..keyboards import CATALOG_TEXT, catalog_keyboard, main_menu_keyboard
from .common import send_fabric_card

router = Router()
BACKEND_UNAVAILABLE = "Каталог временно недоступен. Попробуйте чуть позже."


async def show_catalog_page(
    message: Message,
    api_client: BackendApiClient,
    backend_public_url: str,
    page: int = 0,
) -> None:
    result = await api_client.get_fabrics()
    if not result.ok:
        await message.answer(BACKEND_UNAVAILABLE, reply_markup=main_menu_keyboard())
        return

    fabrics_payload = result.data or []
    fabrics = fabrics_payload.get("items", []) if isinstance(fabrics_payload, dict) else fabrics_payload
    if not fabrics:
        await message.answer("Пока нет опубликованных тканей.", reply_markup=main_menu_keyboard())
        return

    page = max(0, min(page, len(fabrics) - 1))
    fabric = fabrics[page]
    await send_fabric_card(
        message,
        fabric,
        backend_public_url,
        reply_markup=catalog_keyboard(fabric["id"], page, len(fabrics)),
    )


@router.message(Command("catalog"))
@router.message(F.text == CATALOG_TEXT)
async def catalog_command(message: Message, api_client: BackendApiClient, backend_public_url: str) -> None:
    await show_catalog_page(message, api_client, backend_public_url)


@router.callback_query(F.data.startswith("fabric:next:"))
@router.callback_query(F.data.startswith("fabric:prev:"))
async def catalog_nav(callback: CallbackQuery, api_client: BackendApiClient, backend_public_url: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    page = int((callback.data or "").split(":")[-1])
    await show_catalog_page(callback.message, api_client, backend_public_url, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith("fabric:select:"))
async def select_catalog_fabric(callback: CallbackQuery, api_client: BackendApiClient) -> None:
    if callback.from_user is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return
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
