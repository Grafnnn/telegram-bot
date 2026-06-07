"""Observability and safe diagnostic output tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.utils.redaction import (
    REDACTED,
    redact_mapping,
    safe_exception_summary,
    safe_path_for_log,
    sanitize_log_message,
)


def test_redaction_masks_known_secret_keys_case_insensitively() -> None:
    payload = {
        "Authorization": "Bearer admin-token",
        "X-Bot-Token": "bot-token",
        "jwt_secret": "jwt-secret",
        "INITIAL_ADMIN_PASSWORD": "admin-password",
        "openai_api_key": "openai-secret",
        "nested": {"token": "nested-token", "safe": "visible"},
        "photo_bytes": b"raw image bytes",
    }

    redacted = redact_mapping(payload)

    assert redacted["Authorization"] == REDACTED
    assert redacted["X-Bot-Token"] == REDACTED
    assert redacted["jwt_secret"] == REDACTED
    assert redacted["INITIAL_ADMIN_PASSWORD"] == REDACTED
    assert redacted["openai_api_key"] == REDACTED
    assert redacted["nested"]["token"] == REDACTED
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["photo_bytes"] == "[BINARY REDACTED]"


def test_sanitize_log_message_masks_headers_tokens_and_base64() -> None:
    raw = (
        "Authorization: Bearer admin-token X-Bot-Token=bot-token "
        "password=hunter2 token=inline-token api_key=openai-secret "
        "data:image/png;base64,"
        + "A" * 120
    )

    sanitized = sanitize_log_message(raw)

    assert "admin-token" not in sanitized
    assert "bot-token" not in sanitized
    assert "hunter2" not in sanitized
    assert "inline-token" not in sanitized
    assert "openai-secret" not in sanitized
    assert "data:image/png;base64" not in sanitized
    assert REDACTED in sanitized


def test_safe_exception_summary_and_path_hide_sensitive_context() -> None:
    exc = RuntimeError("Authorization: Bearer admin-token password=hunter2")

    summary = safe_exception_summary(exc)
    path = safe_path_for_log("/bot/users/123456789/selection?token=query-secret")

    assert summary.startswith("RuntimeError:")
    assert "admin-token" not in summary
    assert "hunter2" not in summary
    assert path == "/bot/users/{id}/selection"


def test_health_response_does_not_include_config_or_secrets(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "observability-test"})

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "observability-test"
    response_text = response.text
    for forbidden in [
        "JWT_SECRET",
        "BOT_INTERNAL_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY",
        "INITIAL_ADMIN_PASSWORD",
        "admin12345",
        "test_bot_internal_token",
    ]:
        assert forbidden not in response_text
