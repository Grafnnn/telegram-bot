"""Telegram keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Выбрать ткань из каталога")],
            [KeyboardButton(text="Подобрать ткань по описанию")],
            [KeyboardButton(text="Выбрать фасон")],
            [KeyboardButton(text="Загрузить свое фото")],
            [KeyboardButton(text="Мои результаты")],
        ],
        resize_keyboard=True,
    )


def pick_fabric_keyboard(fabric_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Выбрать эту ткань", callback_data=f"pick_fabric:{fabric_id}")]]
    )
