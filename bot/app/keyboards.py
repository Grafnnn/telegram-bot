"""Telegram keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


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


def try_on_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Сгенерировать ещё раз", callback_data="try_on:regenerate")],
            [InlineKeyboardButton(text="📸 Загрузить другое фото", callback_data="try_on:upload_another")],
            [InlineKeyboardButton(text="🧵 Выбрать другую ткань", callback_data="try_on:catalog")],
        ]
    )


def try_on_recovery_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧵 Выбрать другую ткань", callback_data="try_on:catalog")],
            [InlineKeyboardButton(text="📸 Отправить другое фото", callback_data="try_on:upload_another")],
            [InlineKeyboardButton(text="В каталог", callback_data="try_on:catalog")],
        ]
    )
