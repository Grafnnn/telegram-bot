"""Tests for the user-facing photo fabric change menu entry."""

from __future__ import annotations

import asyncio

from app.handlers import start
from app.keyboards import CHANGE_FABRIC_ON_PHOTO_TEXT, main_menu


def run(coro):
    return asyncio.run(coro)


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


def _keyboard_texts(reply_markup) -> list[str]:
    return [button.text for row in reply_markup.keyboard for button in row]


def _inline_callback_data(reply_markup) -> list[str]:
    return [button.callback_data for row in reply_markup.inline_keyboard for button in row]


def test_main_menu_has_change_fabric_on_photo_entry() -> None:
    assert CHANGE_FABRIC_ON_PHOTO_TEXT in _keyboard_texts(main_menu())


def test_change_fabric_on_photo_menu_entry_is_fail_closed() -> None:
    message = FakeMessage(CHANGE_FABRIC_ON_PHOTO_TEXT)

    run(start.change_fabric_on_photo(message))

    assert message.answers
    text, reply_markup = message.answers[-1]
    assert "Поменять ткань на пользовательском фото пока нельзя" in text
    assert "создает новое изображение вместо точного редактирования исходного фото" in text
    assert _inline_callback_data(reply_markup) == ["try_on:catalog"]
