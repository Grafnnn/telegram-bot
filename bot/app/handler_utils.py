"""Shared user-facing bot handler helpers."""

from __future__ import annotations

from uuid import UUID

from app.api_client import BackendAPIError, BackendUnavailableError

BACKEND_UNAVAILABLE_MESSAGE = (
    "Сервис каталога временно недоступен. Попробуйте еще раз чуть позже."
)
INTERNAL_SETUP_MESSAGE = (
    "Внутренняя настройка сервиса временно недоступна. Мы уже знаем, где искать."
)
VALIDATION_MESSAGE = "Не удалось обработать запрос. Обновите выбор и попробуйте снова."
NOT_FOUND_MESSAGE = "Этот вариант больше недоступен. Обновите каталог и попробуйте снова."
UNKNOWN_CALLBACK_MESSAGE = "Эта кнопка больше не актуальна. Откройте меню и попробуйте снова."


def parse_callback_uuid(data: str | None, prefix: str) -> str | None:
    if not data or not data.startswith(prefix):
        return None
    raw_value = data[len(prefix) :]
    if not raw_value:
        return None
    try:
        UUID(raw_value)
    except ValueError:
        return None
    return raw_value


def friendly_api_error_message(exc: Exception) -> str:
    if isinstance(exc, BackendUnavailableError):
        return BACKEND_UNAVAILABLE_MESSAGE
    if isinstance(exc, BackendAPIError):
        if exc.status in {401, 403}:
            return INTERNAL_SETUP_MESSAGE
        if exc.status == 404:
            return NOT_FOUND_MESSAGE
        if exc.status == 422:
            return VALIDATION_MESSAGE
        if exc.status >= 500:
            return BACKEND_UNAVAILABLE_MESSAGE
    return VALIDATION_MESSAGE
