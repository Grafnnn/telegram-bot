from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

ENDPOINT = "/api/internal/crop-only/operator-review/track-a-smoke"
HEADERS = {"X-Bot-Token": "test_bot_internal_token"}


def _post_track_a_smoke(monkeypatch, *, enabled: bool, headers: dict[str, str] | None = None):
    monkeypatch.setenv("CROP_ONLY_OPERATOR_REVIEW_TRACK_A_ENABLED", "true" if enabled else "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        return client.post(ENDPOINT, headers=headers or {})


def test_track_a_fake_provider_smoke_is_disabled_by_default(client) -> None:
    response = client.post(ENDPOINT, headers=HEADERS)

    assert response.status_code == 403
    assert response.json()["detail"] == "Crop-only Track A operator review smoke is disabled."


def test_track_a_fake_provider_smoke_requires_bot_token(monkeypatch) -> None:
    response = _post_track_a_smoke(monkeypatch, enabled=True)

    assert response.status_code == 401


def test_track_a_fake_provider_smoke_returns_redacted_report_when_enabled(monkeypatch) -> None:
    response = _post_track_a_smoke(monkeypatch, enabled=True, headers=HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment_id"] == "crop-only-staging-operator-review-004"
    assert payload["track_id"] == "track_a_fake_provider_staging_route_smoke"
    assert payload["provider_openai_calls"] == 0
    assert payload["controlled_provider_execution"] is False
    assert payload["fake_provider_execution"] is True
    assert payload["user_facing_rollout_approved"] is False
    assert payload["staging_prod_env_touched"] is False
    assert payload["runtime_bot_admin_user_facing_enabled"] is False
    assert payload["imports_sql_direct_db_writes"] is False
    assert payload["real_user_photos_used"] is False
    assert payload["raw_provider_payloads_committed"] is False
    assert payload["fixture_count"] == 4
    assert payload["fixture_ids"] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    assert payload["stop_conditions_enforced"] is True
    assert payload["decision"] == "TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY"
