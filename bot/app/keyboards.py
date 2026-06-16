"""Telegram keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

TRY_ON_RETRY_SAME_FABRIC_CALLBACK = "tryon:retry_same_fabric"
TRY_ON_SEND_NEW_PHOTO_CALLBACK = "tryon:send_new_photo"
TRY_ON_CHOOSE_OTHER_FABRIC_CALLBACK = "tryon:choose_other_fabric"
TRY_ON_CATALOG_CALLBACK = "tryon:catalog"

LEGACY_TRY_ON_REGENERATE_CALLBACK = "try_on:regenerate"
LEGACY_TRY_ON_UPLOAD_ANOTHER_CALLBACK = "try_on:upload_another"
LEGACY_TRY_ON_CATALOG_CALLBACK = "try_on:catalog"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Выбрать ткань из каталога")],
            [KeyboardButton(text="Подобрать ткань по описанию")],
            [KeyboardButton(text="Выбрать фасон")],
            [KeyboardButton(text="Мой выбор")],
            [KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
    )


def select_fabric_keyboard(fabric_id: str, source: str = "fabric") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Выбрать эту ткань", callback_data=f"{source}:select:{fabric_id}")],
            [InlineKeyboardButton(text="🪄 Примерить на моём фото", callback_data=f"{source}:try_on:{fabric_id}")],
        ]
    )


def pick_fabric_keyboard(fabric_id: str) -> InlineKeyboardMarkup:
    return select_fabric_keyboard(fabric_id, "pick")


def try_on_success_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Примерить эту ткань ещё раз",
                    callback_data=TRY_ON_RETRY_SAME_FABRIC_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Выбрать другую ткань",
                    callback_data=TRY_ON_CHOOSE_OTHER_FABRIC_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отправить другое фото",
                    callback_data=TRY_ON_SEND_NEW_PHOTO_CALLBACK,
                )
            ],
            [InlineKeyboardButton(text="В каталог", callback_data=TRY_ON_CATALOG_CALLBACK)],
        ]
    )


def try_on_recovery_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Выбрать другую ткань",
                    callback_data=TRY_ON_CHOOSE_OTHER_FABRIC_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отправить другое фото",
                    callback_data=TRY_ON_SEND_NEW_PHOTO_CALLBACK,
                )
            ],
            [InlineKeyboardButton(text="В каталог", callback_data=TRY_ON_CATALOG_CALLBACK)],
        ]
    )


def try_on_result_keyboard() -> InlineKeyboardMarkup:
    return try_on_success_keyboard()
