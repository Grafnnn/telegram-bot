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
        inline_keyboard=[[InlineKeyboardButton(text="Выбрать эту ткань", callback_data=f"{source}:select:{fabric_id}")]]
    )


def pick_fabric_keyboard(fabric_id: str) -> InlineKeyboardMarkup:
    return select_fabric_keyboard(fabric_id, "pick")
