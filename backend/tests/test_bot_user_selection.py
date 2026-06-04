"""Bot-facing Telegram user fabric selection API tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.telegram_user import TelegramUser

BOT_HEADERS = {"X-Bot-Token": "test_bot_internal_token"}
WRONG_BOT_HEADERS = {"X-Bot-Token": "wrong"}


def _create_fabric(status: str, sku_prefix: str) -> str:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"{sku_prefix}-{uuid4().hex[:10]}",
            name=f"{sku_prefix} fabric",
            category="dress",
            price_per_meter=1200,
            stock_status="in_stock",
            description_for_gpt="Тестовая ткань для выбора в Telegram bot.",
            status=status,
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        return str(fabric.id)


def test_bot_user_routes_require_internal_token(client: TestClient) -> None:
    telegram_id = 750_000_000 + uuid4().int % 1_000_000
    response = client.post("/api/bot/users/upsert", json={"telegram_id": telegram_id})
    assert response.status_code == 401, response.text


def test_bot_user_routes_reject_invalid_internal_token(client: TestClient) -> None:
    telegram_id = 760_000_000 + uuid4().int % 1_000_000
    response = client.post(
        "/api/bot/users/upsert",
        headers=WRONG_BOT_HEADERS,
        json={"telegram_id": telegram_id},
    )
    assert response.status_code == 401, response.text


def test_bot_user_can_select_only_published_fabric(client: TestClient) -> None:
    telegram_id = 900_000_000 + uuid4().int % 1_000_000
    upsert_response = client.post(
        "/api/bot/users/upsert",
        headers=BOT_HEADERS,
        json={"telegram_id": telegram_id, "username": "username", "first_name": "Имя", "last_name": "Фамилия"},
    )
    assert upsert_response.status_code == 200, upsert_response.text
    user_payload = upsert_response.json()
    assert user_payload["telegram_id"] == telegram_id
    assert user_payload["selected_fabric_id"] is None

    with SessionLocal() as db:
        assert db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).one_or_none() is not None

    published_id = _create_fabric("published", "PUB")
    draft_id = _create_fabric("draft", "DRAFT")
    hidden_id = _create_fabric("hidden", "HIDDEN")
    archived_id = _create_fabric("archived", "ARCHIVED")
    missing_id = str(uuid4())

    select_response = client.post(
        f"/api/bot/users/{telegram_id}/selected-fabric",
        headers=BOT_HEADERS,
        json={"fabric_id": published_id},
    )
    assert select_response.status_code == 200, select_response.text
    assert select_response.json()["selected_fabric_id"] == published_id

    selected_response = client.get(f"/api/bot/users/{telegram_id}/selected-fabric", headers=BOT_HEADERS)
    assert selected_response.status_code == 200, selected_response.text
    selected_payload = selected_response.json()
    assert selected_payload["fabric"]["id"] == published_id
    assert selected_payload["fabric"]["images"] == []

    for fabric_id in [draft_id, hidden_id, archived_id]:
        forbidden_response = client.post(
            f"/api/bot/users/{telegram_id}/selected-fabric",
            headers=BOT_HEADERS,
            json={"fabric_id": fabric_id},
        )
        assert forbidden_response.status_code == 403, forbidden_response.text

    missing_response = client.post(
        f"/api/bot/users/{telegram_id}/selected-fabric",
        headers=BOT_HEADERS,
        json={"fabric_id": missing_id},
    )
    assert missing_response.status_code == 404, missing_response.text


def test_bot_selected_fabric_returns_clear_message_when_empty(client: TestClient) -> None:
    telegram_id = 800_000_000 + uuid4().int % 1_000_000
    upsert_response = client.post("/api/bot/users/upsert", headers=BOT_HEADERS, json={"telegram_id": telegram_id})
    assert upsert_response.status_code == 200, upsert_response.text

    selected_response = client.get(f"/api/bot/users/{telegram_id}/selected-fabric", headers=BOT_HEADERS)
    assert selected_response.status_code == 200, selected_response.text
    assert selected_response.json() == {"fabric": None, "message": "Вы пока не выбрали ткань."}
