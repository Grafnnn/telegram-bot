"""Selected fabric, garment style, and catalog-style generation handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import BackendAPIClient, BackendAPIError
from app.config import get_settings
from app.handler_utils import friendly_api_error_message
from app.handlers.fabric_selection import fabric_image_url, format_fabric_card
from app.handlers.garment_styles import format_style_card, style_image_url

router = Router()
GENERATION_CALLBACK = "generation:create_catalog_style"


def backend_client() -> BackendAPIClient:
    return BackendAPIClient(get_settings().backend_api_url)


def generation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Создать визуализацию", callback_data=GENERATION_CALLBACK)]])


def generation_result_url(result_image_url: str | None) -> str | None:
    if not result_image_url:
        return None
    if result_image_url.startswith("/uploads"):
        return f"{get_settings().backend_public_url.rstrip('/')}{result_image_url}"
    return result_image_url


async def answer_photo_or_text(message: Message, image_url: str | None, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    if image_url:
        try:
            await message.answer_photo(image_url, caption=text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup)


@router.message(Command("selected"))
@router.message(lambda message: message.text in {"Моя выбранная ткань", "Мой выбор"})
async def selected_items(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    try:
        data = await backend_client().get_selection(message.from_user.id)
    except BackendAPIError as exc:
        if exc.status == 404:
            await message.answer("Вы пока не выбрали ткань или фасон.")
            return
        await message.answer(friendly_api_error_message(exc))
        return
    except Exception as exc:
        await message.answer(friendly_api_error_message(exc))
        return
    if not data:
        await message.answer("Вы пока не выбрали ткань или фасон.")
        return
    fabric = data.get("fabric")
    style = data.get("garment_style")
    if not fabric and not style:
        await message.answer("Вы пока не выбрали ткань или фасон.")
        return
    if fabric:
        await answer_photo_or_text(message, fabric_image_url(fabric), "Ваша выбранная ткань:\n" + format_fabric_card(fabric))
    else:
        await message.answer("Вы пока не выбрали ткань.")
    if style:
        await answer_photo_or_text(message, style_image_url(style), "Ваш выбранный фасон:\n" + format_style_card(style))
    else:
        await message.answer("Вы пока не выбрали фасон.")
    if fabric and style:
        await message.answer("Ткань и фасон выбраны. Можно создать AI-визуализацию.", reply_markup=generation_keyboard())


@router.callback_query(lambda callback: callback.data == GENERATION_CALLBACK)
async def create_catalog_style_generation(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return
    await callback.answer("Создаю визуализацию…", show_alert=False)
    try:
        result = await backend_client().create_catalog_style_generation(callback.from_user.id)
    except BackendAPIError as exc:
        if callback.message:
            if exc.status in {404, 422}:
                await callback.message.answer("Сначала выберите опубликованную ткань и фасон, затем попробуйте снова.")
            else:
                await callback.message.answer(friendly_api_error_message(exc))
        return
    except Exception as exc:
        if callback.message:
            await callback.message.answer(friendly_api_error_message(exc))
        return
    if not result:
        if callback.message:
            await callback.message.answer("AI-визуализация пока недоступна. Попробуйте еще раз чуть позже.")
        return
    if result.get("status") == "completed":
        image_url = generation_result_url(result.get("result_image_url"))
        text = "Готово! AI-визуализация ткани на выбранном фасоне."
        if callback.message:
            await answer_photo_or_text(callback.message, image_url, text if image_url else f"{text}\n{result.get('result_image_url') or ''}".strip())
        return
    if callback.message:
        await callback.message.answer("AI-визуализация пока недоступна. Попробуйте еще раз чуть позже.")
