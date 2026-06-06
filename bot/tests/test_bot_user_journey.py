"""Bot user journey hardening tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api_client import BackendAPIClient, BackendAPIError, BackendUnavailableError
from app.handler_utils import (
    BACKEND_UNAVAILABLE_MESSAGE,
    INTERNAL_SETUP_MESSAGE,
    UNKNOWN_CALLBACK_MESSAGE,
    VALIDATION_MESSAGE,
    friendly_api_error_message,
    parse_callback_uuid,
)
from app.handlers import catalog, fallback, fabric_selection, selected, start


SECRET_TOKEN = "secret-token-value"


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=1001, username="alice", first_name="Alice", last_name=None)
        self.answers: list[tuple[str, object | None]] = []
        self.photos: list[tuple[str, str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))

    async def answer_photo(self, photo: str, caption: str, reply_markup=None) -> None:
        self.photos.append((photo, caption, reply_markup))


class FakeCallback:
    def __init__(self, data: str | None, message: FakeMessage | None = None) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=1001, username="alice", first_name="Alice", last_name=None)
        self.answers: list[tuple[str, bool | None]] = []

    async def answer(self, text: str, show_alert: bool | None = None) -> None:
        self.answers.append((text, show_alert))


class UnavailableClient:
    async def upsert_user(self, **kwargs):
        raise BackendUnavailableError("backend unavailable")

    async def get_fabrics(self, **kwargs):
        raise BackendUnavailableError("backend unavailable")


class EmptyCatalogClient:
    async def upsert_user(self, **kwargs):
        return {"ok": True}

    async def get_fabrics(self, **kwargs):
        return []


class ForbiddenClient:
    async def upsert_user(self, **kwargs):
        return {"ok": True}

    async def select_fabric(self, telegram_id: int, fabric_id: str):
        raise BackendAPIError(401, "/bot/users/1001/selected-fabric")


class GenerationValidationClient:
    async def create_catalog_style_generation(self, telegram_id: int):
        raise BackendAPIError(422, "/generations/catalog-style")


def run(coro):
    return asyncio.run(coro)


def assert_no_secret_leak(text: str) -> None:
    assert SECRET_TOKEN not in text
    assert "X-Bot-Token" not in text
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "Traceback" not in text


def test_start_shows_welcome_even_when_backend_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(fabric_selection, "backend_client", lambda: UnavailableClient())
    message = FakeMessage("/start")

    run(start.start(message))

    assert message.answers
    assert "Добро пожаловать" in message.answers[0][0]
    assert_no_secret_leak(message.answers[0][0])


def test_catalog_backend_unavailable_and_empty_catalog_are_friendly(monkeypatch) -> None:
    unavailable_message = FakeMessage("Выбрать ткань из каталога")
    monkeypatch.setattr(catalog, "BackendAPIClient", lambda *_args, **_kwargs: UnavailableClient())
    monkeypatch.setattr(fabric_selection, "backend_client", lambda: UnavailableClient())

    run(catalog.show_catalog(unavailable_message))

    assert unavailable_message.answers[-1][0] == BACKEND_UNAVAILABLE_MESSAGE
    assert_no_secret_leak(unavailable_message.answers[-1][0])

    empty_message = FakeMessage("Выбрать ткань из каталога")
    monkeypatch.setattr(catalog, "BackendAPIClient", lambda *_args, **_kwargs: EmptyCatalogClient())
    monkeypatch.setattr(fabric_selection, "backend_client", lambda: EmptyCatalogClient())

    run(catalog.show_catalog(empty_message))

    assert empty_message.answers[-1][0] == "Пока нет опубликованных тканей."


def test_invalid_callback_data_is_rejected_before_backend_call(monkeypatch) -> None:
    def fail_backend_client():
        raise AssertionError("backend should not be called for invalid callback data")

    monkeypatch.setattr(fabric_selection, "backend_client", fail_backend_client)
    callback = FakeCallback("fabric:select:not-a-uuid")

    run(fabric_selection.select_fabric_callback(callback))

    assert callback.answers == [("Эта кнопка больше не актуальна. Откройте каталог заново.", True)]


def test_unknown_callback_gets_controlled_answer() -> None:
    callback = FakeCallback("unexpected:action")

    run(fallback.unknown_callback(callback))

    assert callback.answers == [(UNKNOWN_CALLBACK_MESSAGE, True)]


def test_backend_auth_error_is_friendly_and_does_not_leak_token(monkeypatch) -> None:
    monkeypatch.setattr(fabric_selection, "backend_client", lambda: ForbiddenClient())
    callback = FakeCallback(f"fabric:select:{uuid4()}")

    run(fabric_selection.select_fabric_callback(callback))

    assert callback.answers == [(INTERNAL_SETUP_MESSAGE, True)]
    assert_no_secret_leak(callback.answers[0][0])


def test_generation_without_required_selection_is_controlled(monkeypatch) -> None:
    monkeypatch.setattr(selected, "backend_client", lambda: GenerationValidationClient())
    message = FakeMessage()
    callback = FakeCallback(selected.GENERATION_CALLBACK, message)

    run(selected.create_catalog_style_generation(callback))

    assert callback.answers == [("Создаю визуализацию…", False)]
    assert message.answers[-1][0] == "Сначала выберите опубликованную ткань и фасон, затем попробуйте снова."
    assert_no_secret_leak(message.answers[-1][0])


def test_api_client_sends_internal_token_and_raises_controlled_errors(monkeypatch) -> None:
    captured_headers: list[dict[str, str]] = []

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self):
            return {"items": []}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def request(self, method, url, headers=None, **kwargs):
            captured_headers.append(headers or {})
            return FakeResponse()

    monkeypatch.setattr("app.api_client.aiohttp.ClientSession", FakeSession)

    client = BackendAPIClient("http://backend:8000/api", bot_internal_token=SECRET_TOKEN)
    assert run(client.get_fabrics()) == []
    assert captured_headers[0]["X-Bot-Token"] == SECRET_TOKEN

    assert friendly_api_error_message(BackendAPIError(422, "/bot/users/1/selected-fabric")) == VALIDATION_MESSAGE
    assert_no_secret_leak(friendly_api_error_message(BackendAPIError(401, "/bot/users/1/selected-fabric")))


@pytest.mark.parametrize(
    ("data", "prefix", "expected"),
    [
        (f"fabric:select:{uuid4()}", "fabric:select:", True),
        ("fabric:select:", "fabric:select:", False),
        ("fabric:select:not-a-uuid", "fabric:select:", False),
        ("other:select:not-a-uuid", "fabric:select:", False),
    ],
)
def test_parse_callback_uuid(data: str, prefix: str, expected: bool) -> None:
    assert (parse_callback_uuid(data, prefix) is not None) is expected
