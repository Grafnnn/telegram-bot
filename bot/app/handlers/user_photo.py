"""User-photo fabric try-on handlers."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.api_client import BackendAPIClient, BackendAPIError, BackendUnavailableError
from app.config import get_settings
from app.handler_utils import friendly_api_error_message, parse_callback_uuid
from app.handlers import catalog
from app.handlers.selected import answer_photo_or_text, generation_result_url
from app.keyboards import try_on_result_keyboard
from app.redaction import safe_exception_summary
from app.states import TryOnPhotoStates

router = Router()
logger = logging.getLogger(__name__)

GENERATION_COMPLETED_STATUS = "completed"
GENERATION_ACTIVE_STATUSES = {"pending", "processing"}
PHOTO_SAFETY_COPY = (
    "Загрузите фото, где хорошо видна одежда. "
    "Не отправляйте документы, интимные фото или фото других людей без согласия."
)
GENERATION_PROGRESS_MESSAGE = "Генерирую примерку ткани, это может занять до 1–2 минут…"
GENERATION_UNAVAILABLE_MESSAGE = (
    "Генерация временно не настроена на сервере. Каталог и выбор ткани работают."
)
GENERATION_FAILED_MESSAGE = "Не удалось сгенерировать примерку. Попробуйте ещё раз или выберите другое фото."
GENERATION_TIMEOUT_MESSAGE = "Генерация заняла слишком много времени. Попробуйте ещё раз или загрузите другое фото."
TRY_ON_VALIDATION_MESSAGE = (
    "Не удалось создать примерку. Проверьте, что ткань опубликована и у неё есть текстура, затем попробуйте снова."
)


def backend_client() -> BackendAPIClient:
    return BackendAPIClient(get_settings().backend_api_url)


def _fabric_summary(data: dict[str, Any]) -> str:
    name = data.get("fabric_name") or "выбранная ткань"
    sku = data.get("fabric_sku")
    return f"{name} ({sku})" if sku else str(name)


def _failed_generation_message(result: dict[str, Any] | None) -> str:
    error_message = str((result or {}).get("error_message") or "").lower()
    if "openai api key" in error_message or "не настро" in error_message:
        return GENERATION_UNAVAILABLE_MESSAGE
    return GENERATION_FAILED_MESSAGE


async def _download_telegram_photo(message: Message, file_id: str) -> bytes:
    telegram_file = await message.bot.get_file(file_id)
    downloaded = await message.bot.download_file(telegram_file.file_path)
    if hasattr(downloaded, "seek"):
        downloaded.seek(0)
    if hasattr(downloaded, "read"):
        return downloaded.read()
    return bytes(downloaded)


async def _remember_fabric_for_try_on(state: FSMContext, fabric: dict[str, Any]) -> None:
    await state.update_data(
        fabric_id=str(fabric.get("id") or ""),
        fabric_name=fabric.get("name"),
        fabric_sku=fabric.get("sku"),
    )
    await state.set_state(TryOnPhotoStates.waiting_for_photo)


async def _ask_for_photo(message: Message, state: FSMContext, fabric: dict[str, Any]) -> None:
    await _remember_fabric_for_try_on(state, fabric)
    await message.answer(f"Ткань выбрана для примерки: {_fabric_summary(await state.get_data())}.\n{PHOTO_SAFETY_COPY}")


async def _generate_from_photo(message: Message, state: FSMContext, file_id: str) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    data = await state.get_data()
    fabric_id = data.get("fabric_id")
    if not fabric_id:
        await state.clear()
        await message.answer("Сначала выберите ткань из каталога.")
        return
    await state.update_data(last_photo_file_id=file_id)
    await message.answer(GENERATION_PROGRESS_MESSAGE)
    try:
        photo_bytes = await _download_telegram_photo(message, file_id)
        client = backend_client()
        await client.upsert_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        result = await client.create_user_photo_generation(
            telegram_id=message.from_user.id,
            fabric_id=str(fabric_id),
            photo=photo_bytes,
        )
    except BackendAPIError as exc:
        if exc.status in {400, 404, 422}:
            await message.answer(TRY_ON_VALIDATION_MESSAGE, reply_markup=try_on_result_keyboard())
        else:
            await message.answer(friendly_api_error_message(exc), reply_markup=try_on_result_keyboard())
        return
    except BackendUnavailableError as exc:
        logger.warning("User photo try-on timed out safely: %s", safe_exception_summary(exc))
        await message.answer(GENERATION_TIMEOUT_MESSAGE, reply_markup=try_on_result_keyboard())
        return
    except Exception as exc:
        logger.warning("User photo try-on failed safely: %s", safe_exception_summary(exc))
        await message.answer(GENERATION_UNAVAILABLE_MESSAGE, reply_markup=try_on_result_keyboard())
        return

    generation_status = (result or {}).get("status")
    if generation_status == GENERATION_COMPLETED_STATUS:
        image_url = generation_result_url((result or {}).get("result_image_url"))
        caption = f"Готово! Это AI-примерка ткани: {_fabric_summary(data)}."
        await state.set_state(TryOnPhotoStates.photo_ready)
        await answer_photo_or_text(
            message,
            image_url,
            caption if image_url else f"{caption}\n{(result or {}).get('result_image_url') or ''}".strip(),
            reply_markup=try_on_result_keyboard(),
        )
        return

    await state.set_state(TryOnPhotoStates.photo_ready)
    if generation_status in GENERATION_ACTIVE_STATUSES:
        await message.answer(
            "Примерка запущена. Проверьте результат чуть позже.",
            reply_markup=try_on_result_keyboard(),
        )
        return
    await message.answer(_failed_generation_message(result), reply_markup=try_on_result_keyboard())


@router.callback_query(
    lambda callback: bool(callback.data)
    and (callback.data.startswith("fabric:try_on:") or callback.data.startswith("pick:try_on:"))
)
async def try_on_selected_fabric(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return
    fabric_id = parse_callback_uuid(callback.data, "fabric:try_on:") or parse_callback_uuid(callback.data, "pick:try_on:")
    if fabric_id is None:
        await callback.answer("Эта кнопка больше не актуальна. Откройте каталог заново.", show_alert=True)
        return
    try:
        client = backend_client()
        await client.upsert_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        await client.select_fabric(callback.from_user.id, fabric_id)
        selection = await client.get_selected_fabric(callback.from_user.id)
    except Exception as exc:
        await callback.answer(friendly_api_error_message(exc), show_alert=True)
        return
    fabric = (selection or {}).get("fabric")
    if not fabric:
        await callback.answer("Эта ткань больше недоступна. Откройте каталог заново.", show_alert=True)
        return
    await callback.answer("Ткань выбрана для примерки.", show_alert=False)
    if callback.message:
        await _ask_for_photo(callback.message, state, fabric)


@router.message(lambda message: message.text == "Загрузить свое фото")
async def user_photo_for_selected_fabric(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    try:
        client = backend_client()
        await client.upsert_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        selection = await client.get_selected_fabric(message.from_user.id)
    except Exception as exc:
        await message.answer(friendly_api_error_message(exc))
        return
    fabric = (selection or {}).get("fabric")
    if not fabric:
        await message.answer("Сначала выберите ткань из каталога.")
        return
    await _ask_for_photo(message, state, fabric)


@router.message(TryOnPhotoStates.waiting_for_photo, lambda message: not message.photo)
async def reject_non_photo(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото одним изображением.\n" + PHOTO_SAFETY_COPY)


@router.message(TryOnPhotoStates.waiting_for_photo)
async def handle_try_on_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await reject_non_photo(message)
        return
    await _generate_from_photo(message, state, message.photo[-1].file_id)


@router.callback_query(lambda callback: callback.data == "try_on:upload_another")
async def upload_another_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Жду новое фото.", show_alert=False)
    await state.set_state(TryOnPhotoStates.waiting_for_photo)
    if callback.message:
        await callback.message.answer(PHOTO_SAFETY_COPY)


@router.callback_query(lambda callback: callback.data == "try_on:regenerate")
async def regenerate_try_on(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Повторяю примерку…", show_alert=False)
    data = await state.get_data()
    file_id = data.get("last_photo_file_id")
    if not file_id or callback.message is None:
        await state.set_state(TryOnPhotoStates.waiting_for_photo)
        if callback.message:
            await callback.message.answer("Загрузите фото ещё раз.\n" + PHOTO_SAFETY_COPY)
        return
    await _generate_from_photo(callback.message, state, str(file_id))


@router.callback_query(lambda callback: callback.data == "try_on:catalog")
async def choose_another_fabric(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Открываю каталог.", show_alert=False)
    await state.clear()
    if callback.message:
        await catalog.show_catalog(callback.message)
