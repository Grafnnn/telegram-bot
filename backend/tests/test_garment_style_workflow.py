"""Garment style admin and Telegram selection API tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.garment_style import GarmentStyle

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xde\xa6\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _auth_headers(client: TestClient) -> dict[str, str]:
    login_response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def _create_style(status: str, prefix: str) -> str:
    with SessionLocal() as db:
        style = GarmentStyle(
            name=f"{prefix} style",
            category="dress",
            description="Тестовый фасон для Telegram bot.",
            compatible_fabric_categories=["cotton", "silk"],
            status=status,
        )
        db.add(style)
        db.commit()
        db.refresh(style)
        return str(style.id)


def test_admin_can_create_upload_publish_garment_style_and_see_it_in_public_catalog(client: TestClient) -> None:
    headers = _auth_headers(client)
    payload = {
        "name": f"Платье {uuid4().hex[:8]}",
        "category": "dress",
        "description": "Легкий фасон платья для летнего образа.",
        "compatible_fabric_categories": ["cotton", "silk"],
    }
    create_response = client.post("/api/admin/garment-styles", json=payload, headers=headers)
    assert create_response.status_code == 201, create_response.text
    style = create_response.json()
    style_id = style["id"]
    assert style["status"] == "draft"

    base_response = client.post(
        f"/api/admin/garment-styles/{style_id}/images",
        data={"image_type": "base"},
        files={"file": ("base.png", PNG_1X1, "image/png")},
        headers=headers,
    )
    assert base_response.status_code == 201, base_response.text
    assert base_response.json()["base_image_url"].startswith("/uploads/garment-styles/")

    mask_response = client.post(
        f"/api/admin/garment-styles/{style_id}/images",
        data={"image_type": "mask"},
        files={"file": ("mask.png", PNG_1X1, "image/png")},
        headers=headers,
    )
    assert mask_response.status_code == 201, mask_response.text
    assert mask_response.json()["mask_image_url"].startswith("/uploads/garment-styles/")

    publish_response = client.post(f"/api/admin/garment-styles/{style_id}/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    assert publish_response.json()["status"] == "published"

    draft_response = client.post(
        "/api/admin/garment-styles",
        json={**payload, "name": f"Черновик {uuid4().hex[:8]}"},
        headers=headers,
    )
    assert draft_response.status_code == 201, draft_response.text
    draft_id = draft_response.json()["id"]

    catalog_response = client.get("/api/catalog/garment-styles")
    assert catalog_response.status_code == 200, catalog_response.text
    catalog_ids = {item["id"] for item in catalog_response.json()["items"]}
    assert style_id in catalog_ids
    assert draft_id not in catalog_ids


def test_bot_user_can_select_only_published_garment_style(client: TestClient) -> None:
    telegram_id = 700_000_000 + uuid4().int % 1_000_000
    upsert_response = client.post("/api/bot/users/upsert", json={"telegram_id": telegram_id, "username": "style_user"})
    assert upsert_response.status_code == 200, upsert_response.text
    assert upsert_response.json()["selected_garment_style_id"] is None

    published_id = _create_style("published", "PUB")
    draft_id = _create_style("draft", "DRAFT")
    hidden_id = _create_style("hidden", "HIDDEN")
    archived_id = _create_style("archived", "ARCHIVED")
    missing_id = str(uuid4())

    select_response = client.post(f"/api/bot/users/{telegram_id}/selected-garment-style", json={"garment_style_id": published_id})
    assert select_response.status_code == 200, select_response.text
    assert select_response.json()["selected_garment_style_id"] == published_id

    selected_response = client.get(f"/api/bot/users/{telegram_id}/selected-garment-style")
    assert selected_response.status_code == 200, selected_response.text
    selected_payload = selected_response.json()
    assert selected_payload["garment_style"]["id"] == published_id

    selection_response = client.get(f"/api/bot/users/{telegram_id}/selection")
    assert selection_response.status_code == 200, selection_response.text
    assert selection_response.json()["garment_style"]["id"] == published_id

    for style_id in [draft_id, hidden_id, archived_id]:
        forbidden_response = client.post(f"/api/bot/users/{telegram_id}/selected-garment-style", json={"garment_style_id": style_id})
        assert forbidden_response.status_code == 403, forbidden_response.text

    missing_response = client.post(f"/api/bot/users/{telegram_id}/selected-garment-style", json={"garment_style_id": missing_id})
    assert missing_response.status_code == 404, missing_response.text
