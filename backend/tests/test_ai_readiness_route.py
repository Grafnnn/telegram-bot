from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

ENDPOINT = "/api/internal/ai-readiness/image-generation"
HEADERS = {"X-Bot-Token": "test_bot_internal_token"}


def _get_readiness(monkeypatch, *, api_key: str, headers: dict[str, str] | None = None):
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            return client.get(ENDPOINT, headers=headers or {})
    finally:
        get_settings.cache_clear()


def test_ai_readiness_requires_bot_token(monkeypatch) -> None:
    response = _get_readiness(monkeypatch, api_key="put_openai_key_here")

    assert response.status_code == 401


def test_ai_readiness_blocks_when_openai_key_placeholder(client) -> None:
    response = client.get(ENDPOINT, headers=HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked_missing_openai_api_key"
    assert payload["openai_configured"] is False
    assert payload["provider"] == "OpenAI"
    assert payload["image_model"] == "gpt-image-1"
    assert payload["endpoint"] == "/v1/images/edits"
    assert payload["provider_called"] is False
    assert payload["provider_http_requests"] == 0
    assert payload["secret_values_returned"] is False
    assert payload["raw_provider_payloads_returned"] is False
    assert payload["diagnostic_scope"] == "configuration_only_no_provider_call"
    assert "put_openai_key_here" not in str(payload)


def test_ai_readiness_reports_configured_without_provider_call(monkeypatch) -> None:
    response = _get_readiness(monkeypatch, api_key="test_non_secret_openai_key", headers=HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_for_configured_runtime"
    assert payload["openai_configured"] is True
    assert payload["provider_called"] is False
    assert payload["provider_http_requests"] == 0
    assert payload["secret_values_returned"] is False
    assert "test_non_secret_openai_key" not in str(payload)
    assert payload["user_facing_rollout_approved"] is False
