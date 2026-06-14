"""Bot user journey hardening tests."""

from __future__ import annotations

import asyncio
import io
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api_client import BackendAPIClient, BackendAPIError, BackendUnavailableError, image_upload_metadata
from app.handler_utils import (
    BACKEND_UNAVAILABLE_MESSAGE,
    INTERNAL_SETUP_MESSAGE,
    UNKNOWN_CALLBACK_MESSAGE,
    VALIDATION_MESSAGE,
    friendly_api_error_message,
    parse_callback_uuid,
)
from app.handlers import catalog, fallback, fabric_selection, selected, start, user_photo
from app.states import TryOnPhotoStates
from app.redaction import REDACTED, redact_mapping, safe_exception_summary, sanitize_log_message


SECRET_TOKEN = "secret-token-value"
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xde\xa6\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeBot:
    async def get_file(self, file_id: str):
        return SimpleNamespace(file_path=f"photos/{file_id}.jpg")

    async def download_file(self, file_path: str):
        return io.BytesIO(PNG_1X1)


class FakeMessage:
    def __init__(self, text: str | None = None, photo=None) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=1001, username="alice", first_name="Alice", last_name=None)
        self.photo = photo
        self.bot = FakeBot()
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


class FakeState:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
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


class GenerationResultClient:
    def __init__(self, result: dict | None) -> None:
        self.result = result

    async def create_catalog_style_generation(self, telegram_id: int):
        return self.result


class TryOnSelectionClient:
    def __init__(self) -> None:
        self.fabric_id = str(uuid4())

    async def upsert_user(self, **kwargs):
        return {"ok": True}

    async def select_fabric(self, telegram_id: int, fabric_id: str):
        self.fabric_id = fabric_id
        return {"ok": True}

    async def get_selected_fabric(self, telegram_id: int):
        return {
            "fabric": {
                "id": self.fabric_id,
                "name": "Шелк молочный",
                "sku": "SILK-001",
            }
        }


class TryOnGenerationClient:
    def __init__(self, result: dict | None) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def upsert_user(self, **kwargs):
        return {"ok": True}

    async def create_user_photo_generation(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class TryOnTimeoutClient:
    async def upsert_user(self, **kwargs):
        return {"ok": True}

    async def create_user_photo_generation(self, **kwargs):
        raise BackendUnavailableError("backend timed out")


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


@pytest.mark.parametrize(
    ("result", "expected_message"),
    [
        (
            {"status": "processing", "error_message": f"Traceback X-Bot-Token={SECRET_TOKEN}"},
            selected.GENERATION_PENDING_MESSAGE,
        ),
        (
            {"status": "failed", "error_message": f"provider password={SECRET_TOKEN}"},
            selected.GENERATION_UNAVAILABLE_MESSAGE,
        ),
        (
            {"status": f"unexpected Authorization: Bearer {SECRET_TOKEN}"},
            selected.GENERATION_UNAVAILABLE_MESSAGE,
        ),
    ],
)
def test_generation_status_messages_are_safe(monkeypatch, result, expected_message) -> None:
    monkeypatch.setattr(selected, "backend_client", lambda: GenerationResultClient(result))
    message = FakeMessage()
    callback = FakeCallback(selected.GENERATION_CALLBACK, message)

    run(selected.create_catalog_style_generation(callback))

    assert callback.answers == [("Создаю визуализацию…", False)]
    assert message.answers[-1][0] == expected_message
    assert_no_secret_leak(message.answers[-1][0])


def test_try_on_callback_sets_waiting_photo_state(monkeypatch) -> None:
    client = TryOnSelectionClient()
    monkeypatch.setattr(user_photo, "backend_client", lambda: client)
    message = FakeMessage()
    state = FakeState()
    fabric_id = str(uuid4())
    callback = FakeCallback(f"fabric:try_on:{fabric_id}", message)

    run(user_photo.try_on_selected_fabric(callback, state))

    assert callback.answers == [("Ткань выбрана для примерки.", False)]
    assert state.state == TryOnPhotoStates.waiting_for_photo
    assert state.data["fabric_id"] == fabric_id
    assert state.data["fabric_sku"] == "SILK-001"
    assert "Не отправляйте документы" in message.answers[-1][0]


def test_try_on_non_photo_message_is_rejected_safely() -> None:
    message = FakeMessage("не фото")

    run(user_photo.reject_non_photo(message))

    assert "Пожалуйста, отправьте фото" in message.answers[-1][0]
    assert "Не отправляйте документы" in message.answers[-1][0]
    assert_no_secret_leak(message.answers[-1][0])


def test_try_on_photo_success_sends_generated_result(monkeypatch) -> None:
    client = TryOnGenerationClient({"status": "completed", "result_image_url": "/uploads/generations/result.png"})
    monkeypatch.setattr(user_photo, "backend_client", lambda: client)
    fabric_id = str(uuid4())
    state = FakeState({"fabric_id": fabric_id, "fabric_name": "Шелк молочный", "fabric_sku": "SILK-001"})
    photo = [SimpleNamespace(file_id="low"), SimpleNamespace(file_id="high")]
    message = FakeMessage(photo=photo)

    run(user_photo.handle_try_on_photo(message, state))

    assert client.calls
    assert client.calls[0]["telegram_id"] == 1001
    assert client.calls[0]["fabric_id"] == fabric_id
    assert client.calls[0]["photo"] == PNG_1X1
    assert state.state == TryOnPhotoStates.photo_ready
    assert state.data["last_photo_file_id"] == "high"
    assert message.photos
    assert message.photos[-1][0].endswith("/uploads/generations/result.png")
    assert "AI-примерка ткани" in message.photos[-1][1]


def test_try_on_photo_failure_is_friendly_and_safe(monkeypatch) -> None:
    client = TryOnGenerationClient({"status": "failed", "error_message": f"Traceback X-Bot-Token={SECRET_TOKEN}"})
    monkeypatch.setattr(user_photo, "backend_client", lambda: client)
    state = FakeState({"fabric_id": str(uuid4()), "fabric_name": "Шелк молочный", "fabric_sku": "SILK-001"})
    message = FakeMessage(photo=[SimpleNamespace(file_id="high")])

    run(user_photo.handle_try_on_photo(message, state))

    assert message.answers[-1][0] == user_photo.GENERATION_FAILED_MESSAGE
    assert_no_secret_leak(message.answers[-1][0])


def test_try_on_photo_missing_openai_key_is_friendly(monkeypatch) -> None:
    client = TryOnGenerationClient({"status": "failed", "error_message": "OpenAI API key не настроен"})
    monkeypatch.setattr(user_photo, "backend_client", lambda: client)
    state = FakeState({"fabric_id": str(uuid4()), "fabric_name": "Шелк молочный", "fabric_sku": "SILK-001"})
    message = FakeMessage(photo=[SimpleNamespace(file_id="high")])

    run(user_photo.handle_try_on_photo(message, state))

    assert message.answers[-1][0] == user_photo.GENERATION_UNAVAILABLE_MESSAGE
    assert_no_secret_leak(message.answers[-1][0])


def test_try_on_photo_timeout_is_friendly(monkeypatch) -> None:
    monkeypatch.setattr(user_photo, "backend_client", lambda: TryOnTimeoutClient())
    state = FakeState({"fabric_id": str(uuid4()), "fabric_name": "Шелк молочный", "fabric_sku": "SILK-001"})
    message = FakeMessage(photo=[SimpleNamespace(file_id="high")])

    run(user_photo.handle_try_on_photo(message, state))

    assert message.answers[-1][0] == user_photo.GENERATION_TIMEOUT_MESSAGE
    assert_no_secret_leak(message.answers[-1][0])


def test_api_client_sends_internal_token_and_raises_controlled_errors(monkeypatch) -> None:
    captured_requests: list[tuple[str, str, dict[str, str], object | None]] = []
    captured_timeouts: list[float | None] = []

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
            timeout = kwargs.get("timeout")
            captured_timeouts.append(getattr(timeout, "total", None))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def request(self, method, url, headers=None, **kwargs):
            captured_requests.append((method, url, headers or {}, kwargs.get("data")))
            return FakeResponse()

    monkeypatch.setattr("app.api_client.aiohttp.ClientSession", FakeSession)

    client = BackendAPIClient("http://backend:8000/api", bot_internal_token=SECRET_TOKEN)
    assert run(client.get_fabrics()) == []
    assert captured_requests[0][2]["X-Bot-Token"] == SECRET_TOKEN
    assert captured_timeouts[0] == 10

    assert run(client.create_user_photo_generation(1001, str(uuid4()), PNG_1X1)) == {"items": []}
    assert captured_requests[-1][0] == "POST"
    assert captured_requests[-1][1].endswith("/generations/user-photo")
    assert captured_requests[-1][2]["X-Bot-Token"] == SECRET_TOKEN
    form = captured_requests[-1][3]
    assert form is not None
    fields = getattr(form, "_fields")
    assert [field[0]["name"] for field in fields] == ["telegram_id", "fabric_id", "photo"]
    assert fields[2][0]["filename"] == "telegram-photo.png"
    assert fields[2][1]["Content-Type"] == "image/png"
    assert captured_timeouts[-1] == 180

    assert friendly_api_error_message(BackendAPIError(422, "/bot/users/1/selected-fabric")) == VALIDATION_MESSAGE
    assert_no_secret_leak(friendly_api_error_message(BackendAPIError(401, "/bot/users/1/selected-fabric")))


def test_user_photo_upload_metadata_matches_image_bytes() -> None:
    assert image_upload_metadata(PNG_1X1) == ("telegram-photo.png", "image/png")
    assert image_upload_metadata(b"\xff\xd8\xff\x00") == ("telegram-photo.jpg", "image/jpeg")
    assert image_upload_metadata(b"RIFFxxxxWEBPpayload") == ("telegram-photo.webp", "image/webp")


def test_redaction_masks_bot_headers_and_error_strings() -> None:
    headers = {
        "Authorization": "Bearer admin-token",
        "X-Bot-Token": SECRET_TOKEN,
        "nested": {"password": "admin-password", "safe": "visible"},
    }
    raw_error = (
        "Traceback Authorization: Bearer admin-token X-Bot-Token=secret-token-value "
        "password=hunter2 data:image/png;base64,"
        + "A" * 120
    )

    redacted_headers = redact_mapping(headers)
    summary = safe_exception_summary(RuntimeError(raw_error))
    sanitized = sanitize_log_message(raw_error)

    assert redacted_headers["Authorization"] == REDACTED
    assert redacted_headers["X-Bot-Token"] == REDACTED
    assert redacted_headers["nested"]["password"] == REDACTED
    assert redacted_headers["nested"]["safe"] == "visible"
    for text in [summary, sanitized]:
        assert "admin-token" not in text
        assert SECRET_TOKEN not in text
        assert "hunter2" not in text
        assert "data:image/png;base64" not in text


def test_api_client_logs_safe_context_without_token_or_personal_ids(monkeypatch, caplog) -> None:
    class FakeResponse:
        status = 500

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self):
            return {"error": "Authorization: Bearer admin-token"}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def request(self, method, url, headers=None, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.api_client.aiohttp.ClientSession", FakeSession)

    client = BackendAPIClient("http://backend:8000/api", bot_internal_token=SECRET_TOKEN)
    with caplog.at_level(logging.ERROR, logger="app.api_client"):
        with pytest.raises(BackendAPIError):
            run(client.get_selection(123456789))

    assert "Backend error 500" in caplog.text
    assert SECRET_TOKEN not in caplog.text
    assert "X-Bot-Token" not in caplog.text
    assert "123456789" not in caplog.text
    assert "/bot/users/{id}/selection" in caplog.text


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
