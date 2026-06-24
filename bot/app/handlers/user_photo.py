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
from app.keyboards import (
    CHANGE_FABRIC_ON_PHOTO_TEXT,
    try_on_disabled_keyboard,
    try_on_entry_keyboard,
    try_on_mask_preset_keyboard,
    try_on_recovery_keyboard,
    try_on_result_keyboard,
)
from app.redaction import safe_exception_summary
from app.states import TryOnPhotoStates

router = Router()
logger = logging.getLogger(__name__)

GENERATION_COMPLETED_STATUS = "completed"
GENERATION_ACTIVE_STATUSES = {"pending", "processing"}
GENERATION_FAILURE_OPENAI_NOT_CONFIGURED = "openai_not_configured"
GENERATION_FAILURE_PROVIDER_UNAVAILABLE = "provider_unavailable"
GENERATION_FAILURE_MASK_REQUIRED = "mask_required"
GENERATION_FAILURE_PRESERVATION = "preservation_failed"
GENERATION_FAILURE_UNKNOWN = "unknown"
PHOTO_SAFETY_COPY = (
    "Загрузите фото, где хорошо видна одежда. "
    "Не отправляйте документы, интимные фото или фото других людей без согласия."
)
GENERATION_PROGRESS_MESSAGE = "Генерирую примерку ткани, это может занять до 1–2 минут…"
GENERATION_UNAVAILABLE_MESSAGE = (
    "Генерация временно не настроена на сервере. Каталог и выбор ткани работают."
)
GENERATION_PROVIDER_UNAVAILABLE_MESSAGE = "AI-визуализация пока недоступна. Попробуйте еще раз чуть позже."
GENERATION_FAILED_MESSAGE = "Не удалось сгенерировать примерку. Попробуйте ещё раз или выберите другое фото."
GENERATION_TIMEOUT_MESSAGE = "Генерация заняла слишком много времени. Попробуйте ещё раз или загрузите другое фото."
TRY_ON_VALIDATION_MESSAGE = (
    "Не удалось заменить ткань на фото. Попробуйте другое фото: одежда должна быть хорошо видна."
)
TRY_ON_NO_REFERENCE_IMAGE_MESSAGE = "У выбранной ткани нет изображения для примерки. Выберите другую ткань."
TRY_ON_MASK_REQUIRED_MESSAGE = (
    "Я не буду перерисовывать всё фото целиком. Для точной примерки нужно выделить область одежды. "
    "Сейчас можно выбрать другую ткань или отправить другое фото."
)
TRY_ON_NO_FABRIC_MESSAGE = "Сначала выберите ткань из каталога, затем отправьте фото."
TRY_ON_START_NO_FABRIC_MESSAGE = "Сначала выберите ткань из каталога, затем я смогу заменить ткань на фото."
TRY_ON_GUIDED_INTRO_MESSAGE = (
    "Безопасная замена ткани работает по шагам:\n"
    "1. Сначала выберите ткань из каталога.\n"
    "2. Затем отправьте фото, где хорошо видна одежда.\n"
    "3. После фото нужно явно выбрать область одежды, которую можно менять.\n\n"
    "Без выбранной области одежды AI не запускается."
)
TRY_ON_PHOTO_MASK_PRESET_MESSAGE = (
    "Отметьте область одежды для замены ткани. Сейчас доступен безопасный режим: "
    "ответьте одним сообщением с номером зоны или выберите видимую футболку/внутреннюю одежду "
    "под расстёгнутой рубашкой."
)
TRY_ON_PRESET_VALIDATION_MESSAGE = (
    "Не удалось безопасно заменить ткань на этом фото. Попробуйте фото, где видимая футболка или внутренняя "
    "одежда хорошо освещена по центру кадра, или выберите другую ткань."
)
TRY_ON_DISABLED_MESSAGE = (
    "Примерка на пользовательском фото временно отключена: мы не будем запускать режим, "
    "который может исказить человека или фон. Каталог тканей и выбор ткани работают."
)
TRY_ON_SAFE_ENTRY_MESSAGE = (
    "Полное фото пока не поддерживается безопасно: мы не будем отправлять в AI лицо, фон или человека целиком.\n\n"
    "Безопасный MVP сейчас работает только с крупным фрагментом одежды без лица и фона."
)
TRY_ON_CROP_INSTRUCTION_MESSAGE = (
    "Отправьте крупный фрагмент одежды без лица и фона. "
    "Сейчас безопасная примерка работает только с таким кропом."
)
TRY_ON_FULL_PHOTO_UNSUPPORTED_MESSAGE = (
    "Полное фото пока не поддерживается безопасно. "
    "Отправьте крупный фрагмент одежды или вернитесь в каталог."
)
INPUT_MODE_FULL_PHOTO = "full_photo"
INPUT_MODE_GARMENT_CROP = "garment_crop"
MASK_PRESET_CENTRAL_UPPER_GARMENT = "central_upper_garment"
MASK_PRESET_VISIBLE_INNER_TSHIRT = "visible_inner_tshirt"
MASK_PRESET_DEFAULT = MASK_PRESET_VISIBLE_INNER_TSHIRT


def backend_client() -> BackendAPIClient:
    return BackendAPIClient(get_settings().backend_api_url)


def _user_photo_try_on_enabled() -> bool:
    return get_settings().user_photo_try_on_enabled


def _garment_crop_try_on_enabled() -> bool:
    return get_settings().user_photo_garment_crop_try_on_enabled


def _fabric_summary(data: dict[str, Any]) -> str:
    name = data.get("fabric_name") or "выбранная ткань"
    sku = data.get("fabric_sku")
    return f"{name} ({sku})" if sku else str(name)


def _generation_failure_reason(result: dict[str, Any] | None) -> str:
    error_message = str((result or {}).get("error_message") or "").lower()
    if "openai api key" in error_message or "openai_api_key" in error_message or "не настро" in error_message:
        return GENERATION_FAILURE_OPENAI_NOT_CONFIGURED
    if _is_mask_required_error(error_message):
        return GENERATION_FAILURE_MASK_REQUIRED
    if "сохранить исходное фото" in error_message or "protected regions" in error_message or "preservation" in error_message:
        return GENERATION_FAILURE_PRESERVATION
    if "ai-визуализация" in error_message or "provider" in error_message or "urlerror" in error_message:
        return GENERATION_FAILURE_PROVIDER_UNAVAILABLE
    return GENERATION_FAILURE_UNKNOWN


def _failed_generation_message(result: dict[str, Any] | None) -> str:
    reason = _generation_failure_reason(result)
    if reason == GENERATION_FAILURE_OPENAI_NOT_CONFIGURED:
        return GENERATION_UNAVAILABLE_MESSAGE
    if reason == GENERATION_FAILURE_MASK_REQUIRED:
        return TRY_ON_MASK_REQUIRED_MESSAGE
    if reason == GENERATION_FAILURE_PRESERVATION:
        return TRY_ON_PRESET_VALIDATION_MESSAGE
    if reason == GENERATION_FAILURE_PROVIDER_UNAVAILABLE:
        return GENERATION_PROVIDER_UNAVAILABLE_MESSAGE
    return GENERATION_FAILED_MESSAGE


def _is_mask_required_error(detail: str) -> bool:
    normalized = detail.lower()
    return (
        "маска области одежды" in normalized
        or "clothing mask provider is not configured" in normalized
        or "user photo mask is not valid" in normalized
    )


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
    if not _user_photo_try_on_enabled():
        if _garment_crop_try_on_enabled():
            await _remember_fabric_for_try_on(state, fabric)
            await state.update_data(input_mode=INPUT_MODE_GARMENT_CROP)
            await message.answer(TRY_ON_SAFE_ENTRY_MESSAGE, reply_markup=try_on_entry_keyboard())
            return
        await state.clear()
        await message.answer(TRY_ON_DISABLED_MESSAGE, reply_markup=try_on_disabled_keyboard())
        return
    await _remember_fabric_for_try_on(state, fabric)
    await state.update_data(input_mode=INPUT_MODE_FULL_PHOTO)
    await message.answer(
        f"Ткань выбрана: {_fabric_summary(await state.get_data())}. "
        "Теперь отправьте фото, где нужно заменить ткань на одежде.\n"
        f"{PHOTO_SAFETY_COPY}"
    )


async def _start_guided_photo_flow(message: Message, state: FSMContext) -> None:
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
        logger.warning("Selected fabric lookup for guided try-on failed safely: %s", safe_exception_summary(exc))
        selection = None
    fabric = (selection or {}).get("fabric")
    if not fabric:
        await state.clear()
        await message.answer(TRY_ON_GUIDED_INTRO_MESSAGE)
        await message.answer(TRY_ON_START_NO_FABRIC_MESSAGE, reply_markup=try_on_disabled_keyboard())
        return
    await _remember_fabric_for_try_on(state, fabric)
    await state.update_data(input_mode=INPUT_MODE_FULL_PHOTO)
    await message.answer(
        f"Ткань выбрана: {_fabric_summary(await state.get_data())}.\n"
        "Теперь отправьте фото, где нужно заменить ткань на одежде.\n"
        f"{PHOTO_SAFETY_COPY}"
    )


async def _generate_from_photo(
    message: Message,
    state: FSMContext,
    file_id: str,
    *,
    input_mode: str = INPUT_MODE_FULL_PHOTO,
    mask_preset: str | None = None,
) -> None:
    if input_mode == INPUT_MODE_GARMENT_CROP:
        if not _garment_crop_try_on_enabled():
            await state.clear()
            await message.answer(TRY_ON_DISABLED_MESSAGE, reply_markup=try_on_disabled_keyboard())
            return
    elif not _user_photo_try_on_enabled() and not mask_preset:
        await state.clear()
        await message.answer(TRY_ON_FULL_PHOTO_UNSUPPORTED_MESSAGE, reply_markup=try_on_entry_keyboard())
        return
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    data = await state.get_data()
    fabric_id = data.get("fabric_id")
    if not fabric_id:
        await state.clear()
        await message.answer(TRY_ON_NO_FABRIC_MESSAGE)
        return
    await state.update_data(last_photo_file_id=file_id)
    await state.update_data(input_mode=input_mode)
    await message.answer(
        "Генерирую примерку ткани для фрагмента одежды, это может занять до 1–2 минут…"
        if input_mode == INPUT_MODE_GARMENT_CROP
        else GENERATION_PROGRESS_MESSAGE
    )
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
            input_mode=input_mode,
            mask_preset=mask_preset,
        )
    except BackendAPIError as exc:
        if exc.status in {400, 404, 422}:
            if exc.detail and _is_mask_required_error(exc.detail):
                await message.answer(TRY_ON_MASK_REQUIRED_MESSAGE, reply_markup=try_on_recovery_keyboard())
            elif exc.detail and "изображения для примерки" in exc.detail:
                await message.answer(TRY_ON_NO_REFERENCE_IMAGE_MESSAGE, reply_markup=try_on_result_keyboard())
            else:
                await message.answer(TRY_ON_PRESET_VALIDATION_MESSAGE, reply_markup=try_on_result_keyboard())
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
        caption = (
            f"Готово! Это AI-примерка ткани на фрагменте одежды: {_fabric_summary(data)}."
            if input_mode == INPUT_MODE_GARMENT_CROP
            else f"Готово! Это AI-примерка ткани: {_fabric_summary(data)}."
        )
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
    logger.warning(
        "User photo try-on returned failed status reason=%s",
        _generation_failure_reason(result),
    )
    await message.answer(_failed_generation_message(result), reply_markup=try_on_result_keyboard())


async def _ask_for_mask_preset(message: Message, state: FSMContext, file_id: str) -> None:
    await state.update_data(last_photo_file_id=file_id, input_mode=INPUT_MODE_FULL_PHOTO)
    await state.set_state(TryOnPhotoStates.waiting_for_mask_preset)
    try:
        await message.answer_photo(
            file_id,
            caption=TRY_ON_PHOTO_MASK_PRESET_MESSAGE,
            reply_markup=try_on_mask_preset_keyboard(),
        )
    except Exception as exc:
        logger.warning("Failed to echo try-on photo safely: %s", safe_exception_summary(exc))
        await message.answer(TRY_ON_PHOTO_MASK_PRESET_MESSAGE, reply_markup=try_on_mask_preset_keyboard())


@router.callback_query(
    lambda callback: bool(callback.data)
    and (callback.data.startswith("fabric:try_on:") or callback.data.startswith("pick:try_on:"))
)
async def try_on_selected_fabric(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return
    fabric_id = parse_callback_uuid(callback.data, "fabric:try_on:") or parse_callback_uuid(
        callback.data, "pick:try_on:"
    )
    if fabric_id is None:
        await callback.answer("Эта кнопка больше не актуальна. Откройте каталог заново.", show_alert=True)
        return
    if not _user_photo_try_on_enabled() and not _garment_crop_try_on_enabled():
        await state.clear()
        await callback.answer("Примерка на фото временно отключена.", show_alert=True)
        if callback.message:
            await callback.message.answer(TRY_ON_DISABLED_MESSAGE, reply_markup=try_on_disabled_keyboard())
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
    if _user_photo_try_on_enabled():
        await callback.answer("Ткань выбрана для примерки.", show_alert=False)
        if callback.message:
            await _ask_for_photo(callback.message, state, fabric)
        return
    await callback.answer("Выберите безопасный режим примерки.", show_alert=False)
    await _remember_fabric_for_try_on(state, fabric)
    await state.update_data(input_mode=INPUT_MODE_GARMENT_CROP)
    if callback.message:
        await callback.message.answer(TRY_ON_SAFE_ENTRY_MESSAGE, reply_markup=try_on_entry_keyboard())


@router.message(lambda message: message.text == CHANGE_FABRIC_ON_PHOTO_TEXT)
async def change_fabric_on_photo(message: Message, state: FSMContext) -> None:
    await _start_guided_photo_flow(message, state)


@router.message(lambda message: message.text == "Загрузить свое фото")
async def user_photo_for_selected_fabric(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    if not _user_photo_try_on_enabled():
        if _garment_crop_try_on_enabled():
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
                await message.answer(TRY_ON_NO_FABRIC_MESSAGE)
                return
            await _remember_fabric_for_try_on(state, fabric)
            await state.update_data(input_mode=INPUT_MODE_GARMENT_CROP)
            await message.answer(TRY_ON_SAFE_ENTRY_MESSAGE, reply_markup=try_on_entry_keyboard())
            return
        await state.clear()
        await message.answer(TRY_ON_DISABLED_MESSAGE, reply_markup=try_on_disabled_keyboard())
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
        await message.answer(TRY_ON_NO_FABRIC_MESSAGE)
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
    data = await state.get_data()
    if not data.get("fabric_id"):
        await state.clear()
        await message.answer(TRY_ON_NO_FABRIC_MESSAGE)
        return
    await _ask_for_mask_preset(message, state, message.photo[-1].file_id)


@router.message(
    TryOnPhotoStates.waiting_for_mask_preset,
    lambda message: bool(message.text)
    and message.text.strip().lower() in {"1", "верх", "верхняя одежда", "рубашка", "куртка"},
)
async def handle_mask_preset_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    file_id = data.get("last_photo_file_id")
    if not file_id:
        await state.set_state(TryOnPhotoStates.waiting_for_photo)
        await message.answer("Загрузите фото ещё раз.\n" + PHOTO_SAFETY_COPY)
        return
    await state.update_data(mask_preset=MASK_PRESET_DEFAULT)
    await _generate_from_photo(
        message,
        state,
        str(file_id),
        input_mode=INPUT_MODE_FULL_PHOTO,
        mask_preset=MASK_PRESET_DEFAULT,
    )


@router.message(TryOnPhotoStates.waiting_for_mask_preset)
async def reject_mask_preset_text(message: Message) -> None:
    await message.answer(TRY_ON_PHOTO_MASK_PRESET_MESSAGE, reply_markup=try_on_mask_preset_keyboard())


@router.message(TryOnPhotoStates.waiting_for_garment_crop, lambda message: not message.photo)
async def reject_non_garment_crop_photo(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте крупный фрагмент одежды одним изображением.")


@router.message(TryOnPhotoStates.waiting_for_garment_crop)
async def handle_garment_crop_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await reject_non_garment_crop_photo(message)
        return
    await _generate_from_photo(
        message,
        state,
        message.photo[-1].file_id,
        input_mode=INPUT_MODE_GARMENT_CROP,
    )


@router.callback_query(lambda callback: callback.data == "try_on:garment_crop")
async def start_garment_crop_try_on(callback: CallbackQuery, state: FSMContext) -> None:
    if not _garment_crop_try_on_enabled():
        await callback.answer("Безопасная примерка временно отключена.", show_alert=True)
        return
    await callback.answer("Жду фрагмент одежды.", show_alert=False)
    await state.update_data(input_mode=INPUT_MODE_GARMENT_CROP)
    await state.set_state(TryOnPhotoStates.waiting_for_garment_crop)
    if callback.message:
        await callback.message.answer(TRY_ON_CROP_INSTRUCTION_MESSAGE)


@router.callback_query(lambda callback: callback.data == "try_on:upload_another")
async def upload_another_photo(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("input_mode") == INPUT_MODE_GARMENT_CROP:
        await callback.answer("Жду новый фрагмент одежды.", show_alert=False)
        await state.set_state(TryOnPhotoStates.waiting_for_garment_crop)
        if callback.message:
            await callback.message.answer(TRY_ON_CROP_INSTRUCTION_MESSAGE)
        return
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
        input_mode = data.get("input_mode")
        await state.set_state(
            TryOnPhotoStates.waiting_for_garment_crop
            if input_mode == INPUT_MODE_GARMENT_CROP
            else TryOnPhotoStates.waiting_for_photo
        )
        if callback.message:
            await callback.message.answer(
                TRY_ON_CROP_INSTRUCTION_MESSAGE
                if input_mode == INPUT_MODE_GARMENT_CROP
                else "Загрузите фото ещё раз.\n" + PHOTO_SAFETY_COPY
            )
        return
    await _generate_from_photo(
        callback.message,
        state,
        str(file_id),
        input_mode=data.get("input_mode") or INPUT_MODE_FULL_PHOTO,
        mask_preset=data.get("mask_preset"),
    )


@router.callback_query(
    lambda callback: callback.data in {"try_on:preset:central_upper_garment", "try_on:preset:visible_inner_tshirt"}
)
async def use_central_upper_garment_preset(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Запускаю безопасную замену выбранной области.", show_alert=False)
    data = await state.get_data()
    file_id = data.get("last_photo_file_id")
    if not file_id or callback.message is None:
        await state.set_state(TryOnPhotoStates.waiting_for_photo)
        if callback.message:
            await callback.message.answer("Загрузите фото ещё раз.\n" + PHOTO_SAFETY_COPY)
        return
    selected_preset = (
        MASK_PRESET_CENTRAL_UPPER_GARMENT
        if callback.data == "try_on:preset:central_upper_garment"
        else MASK_PRESET_DEFAULT
    )
    await state.update_data(mask_preset=selected_preset)
    await _generate_from_photo(
        callback.message,
        state,
        str(file_id),
        input_mode=INPUT_MODE_FULL_PHOTO,
        mask_preset=selected_preset,
    )


@router.callback_query(lambda callback: callback.data == "try_on:cancel")
async def cancel_try_on(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Отменено.", show_alert=False)
    await state.clear()
    if callback.message:
        await callback.message.answer("Примерка отменена.", reply_markup=try_on_disabled_keyboard())


@router.callback_query(lambda callback: callback.data == "try_on:catalog")
async def choose_another_fabric(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Открываю каталог.", show_alert=False)
    await state.clear()
    if callback.message:
        await catalog.show_catalog(callback.message)
