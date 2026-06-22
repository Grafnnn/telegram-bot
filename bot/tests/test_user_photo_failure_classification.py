from __future__ import annotations

from app.handlers.user_photo import (
    GENERATION_FAILED_MESSAGE,
    GENERATION_PROVIDER_UNAVAILABLE_MESSAGE,
    GENERATION_UNAVAILABLE_MESSAGE,
    TRY_ON_MASK_REQUIRED_MESSAGE,
    _failed_generation_message,
    _generation_failure_reason,
)


def test_failed_generation_message_for_missing_openai_key() -> None:
    result = {"error_message": "AI-визуализация пока недоступна: OpenAI API key не настроен."}

    assert _generation_failure_reason(result) == "openai_not_configured"
    assert _failed_generation_message(result) == GENERATION_UNAVAILABLE_MESSAGE


def test_failed_generation_message_for_provider_transport_error() -> None:
    result = {"error_message": "provider_call_failed:URLError"}

    assert _generation_failure_reason(result) == "provider_unavailable"
    assert _failed_generation_message(result) == GENERATION_PROVIDER_UNAVAILABLE_MESSAGE


def test_failed_generation_message_for_mask_required_error() -> None:
    result = {"error_message": "Clothing mask provider is not configured for strict edit."}

    assert _generation_failure_reason(result) == "mask_required"
    assert _failed_generation_message(result) == TRY_ON_MASK_REQUIRED_MESSAGE


def test_failed_generation_message_for_unknown_error() -> None:
    result = {"error_message": "unexpected redacted generation failure"}

    assert _generation_failure_reason(result) == "unknown"
    assert _failed_generation_message(result) == GENERATION_FAILED_MESSAGE
