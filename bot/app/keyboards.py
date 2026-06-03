"""Telegram keyboards."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


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
