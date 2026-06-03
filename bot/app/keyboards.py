from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

CATALOG_TEXT = "Выбрать ткань из каталога"
PICK_TEXT = "Подобрать ткань по описанию"
SELECTED_TEXT = "Моя выбранная ткань"
HELP_TEXT = "Помощь"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CATALOG_TEXT)],
            [KeyboardButton(text=PICK_TEXT)],
            [KeyboardButton(text=SELECTED_TEXT), KeyboardButton(text=HELP_TEXT)],
        ],
        resize_keyboard=True,
    )


def catalog_keyboard(fabric_id: str, page: int, total: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Выбрать эту ткань", callback_data=f"fabric:select:{fabric_id}")]]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=f"fabric:prev:{page - 1}"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="Следующая", callback_data=f"fabric:next:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recommendation_keyboard(fabric_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Выбрать эту ткань", callback_data=f"pick:select:{fabric_id}")]]
    )
