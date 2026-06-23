"""Tests for the user-facing photo fabric change menu entry."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.handlers import user_photo
from app.keyboards import CHANGE_FABRIC_ON_PHOTO_TEXT, main_menu


def run(coro):
    return asyncio.run(coro)


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=1001, username="alice", first_name="Alice", last_name=None)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class FakeState:
    def __init__(self) -> None:
        self.data = {}
        self.state = None
        self.cleared = False

    async def set_state(self, state) -> None:
        self.state = state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def clear(self) -> None:
        self.data.clear()
        self.state = None
        self.cleared = True


class NoSelectedFabricClient:
    async def upsert_user(self, **kwargs):
        return {"ok": True}

    async def get_selected_fabric(self, telegram_id: int):
        return {"fabric": None}


def _keyboard_texts(reply_markup) -> list[str]:
    return [button.text for row in reply_markup.keyboard for button in row]


def _inline_callback_data(reply_markup) -> list[str]:
    return [button.callback_data for row in reply_markup.inline_keyboard for button in row]


def test_main_menu_has_change_fabric_on_photo_entry() -> None:
    assert CHANGE_FABRIC_ON_PHOTO_TEXT in _keyboard_texts(main_menu())


def test_change_fabric_on_photo_menu_entry_guides_to_catalog(monkeypatch) -> None:
    monkeypatch.setattr(user_photo, "backend_client", lambda: NoSelectedFabricClient())
    message = FakeMessage(CHANGE_FABRIC_ON_PHOTO_TEXT)
    state = FakeState()

    run(user_photo.change_fabric_on_photo(message, state))

    assert len(message.answers) == 2
    assert "Без выбранной области одежды AI не запускается" in message.answers[0][0]
    text, reply_markup = message.answers[-1]
    assert text == user_photo.TRY_ON_START_NO_FABRIC_MESSAGE
    assert _inline_callback_data(reply_markup) == ["try_on:catalog"]
