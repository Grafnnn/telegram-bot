"""Catalog admin CRUD hardening tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.models import Admin, Fabric, FabricImage
from app.models.garment_style import GarmentStyle
from app.utils.security import hash_password
from tests.test_fabric_admin_workflow import PNG_1X1


def _login(client: TestClient, email: str = "admin@example.com", password: str = "admin12345") -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_viewer(email: str, password: str = "viewer-password") -> None:
    with SessionLocal() as db:
        db.add(
            Admin(
                email=email,
                password_hash=hash_password(password),
                full_name="Catalog Viewer",
                role="viewer",
                is_active=True,
            )
        )
        db.commit()


def _fabric_payload(**overrides) -> dict:
    payload = {
        "sku": f"CRUD-{uuid4().hex[:10]}",
        "name": "CRUD fabric",
        "category": "cotton",
        "price_per_meter": 1200,
        "stock_status": "in_stock",
        "description_for_gpt": "Тестовая ткань для CRUD hardening.",
    }
    payload.update(overrides)
    return payload


def _style_payload(**overrides) -> dict:
    payload = {
        "name": f"CRUD style {uuid4().hex[:8]}",
        "category": "dress",
        "description": "Тестовый фасон для CRUD hardening.",
    }
    payload.update(overrides)
    return payload


def _add_ready_fabric_images(db, fabric: Fabric) -> None:
    for sort_order, image_type in enumerate(["main", "texture"]):
        image_url = f"/uploads/fabrics/{fabric.id}-{image_type}.png"
        image_path = get_settings().upload_dir / image_url.removeprefix("/uploads/")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(PNG_1X1)
        db.add(FabricImage(fabric_id=fabric.id, image_url=image_url, image_type=image_type, sort_order=sort_order))


def test_admin_fabric_crud_auth_validation_conflicts_and_not_found(client: TestClient) -> None:
    admin_headers = _auth_headers(_login(client))
    viewer_email = f"viewer-{uuid4().hex[:8]}@example.com"
    _create_viewer(viewer_email)
    viewer_headers = _auth_headers(_login(client, viewer_email, "viewer-password"))

    assert client.post("/api/admin/fabrics", json=_fabric_payload()).status_code == 401
    assert client.post("/api/admin/fabrics", json=_fabric_payload(), headers=viewer_headers).status_code == 403

    valid_response = client.post("/api/admin/fabrics", json=_fabric_payload(), headers=admin_headers)
    assert valid_response.status_code == 201, valid_response.text
    first_fabric = valid_response.json()

    missing_required = client.post(
        "/api/admin/fabrics",
        json={"sku": f"MISS-{uuid4().hex[:8]}", "category": "cotton"},
        headers=admin_headers,
    )
    assert missing_required.status_code == 422, missing_required.text

    blank_required = client.post(
        "/api/admin/fabrics",
        json=_fabric_payload(sku="   "),
        headers=admin_headers,
    )
    assert blank_required.status_code == 422, blank_required.text

    negative_price = client.post(
        "/api/admin/fabrics",
        json=_fabric_payload(price_per_meter=-1),
        headers=admin_headers,
    )
    assert negative_price.status_code == 422, negative_price.text

    invalid_status = client.post(
        "/api/admin/fabrics",
        json=_fabric_payload(status="published-ish"),
        headers=admin_headers,
    )
    assert invalid_status.status_code == 422, invalid_status.text

    invalid_stock = client.post(
        "/api/admin/fabrics",
        json=_fabric_payload(stock_status="available"),
        headers=admin_headers,
    )
    assert invalid_stock.status_code == 422, invalid_stock.text

    invalid_query_status = client.get("/api/admin/fabrics?status=published-ish", headers=admin_headers)
    assert invalid_query_status.status_code == 422, invalid_query_status.text

    duplicate_create = client.post(
        "/api/admin/fabrics",
        json=_fabric_payload(sku=first_fabric["sku"]),
        headers=admin_headers,
    )
    assert duplicate_create.status_code == 409, duplicate_create.text

    second_response = client.post("/api/admin/fabrics", json=_fabric_payload(), headers=admin_headers)
    assert second_response.status_code == 201, second_response.text
    second_fabric = second_response.json()

    duplicate_update = client.patch(
        f"/api/admin/fabrics/{second_fabric['id']}",
        json={"sku": first_fabric["sku"]},
        headers=admin_headers,
    )
    assert duplicate_update.status_code == 409, duplicate_update.text

    missing_id = str(uuid4())
    assert client.get(f"/api/admin/fabrics/{missing_id}", headers=admin_headers).status_code == 404
    assert client.patch(f"/api/admin/fabrics/{missing_id}", json={"name": "missing"}, headers=admin_headers).status_code == 404
    assert client.delete(f"/api/admin/fabrics/{missing_id}", headers=admin_headers).status_code == 404

    invalid_image_type = client.post(
        f"/api/admin/fabrics/{first_fabric['id']}/images",
        data={"image_type": "avatar", "sort_order": "0"},
        files={"file": ("avatar.png", PNG_1X1, "image/png")},
        headers=admin_headers,
    )
    assert invalid_image_type.status_code == 400, invalid_image_type.text

    invalid_sort_order = client.post(
        f"/api/admin/fabrics/{first_fabric['id']}/images",
        data={"image_type": "main", "sort_order": "-1"},
        files={"file": ("main.png", PNG_1X1, "image/png")},
        headers=admin_headers,
    )
    assert invalid_sort_order.status_code == 422, invalid_sort_order.text


def test_admin_garment_style_crud_validation_conflicts_and_not_found(client: TestClient) -> None:
    admin_headers = _auth_headers(_login(client))

    assert client.get("/api/admin/garment-styles").status_code == 401

    valid_response = client.post("/api/admin/garment-styles", json=_style_payload(), headers=admin_headers)
    assert valid_response.status_code == 201, valid_response.text
    style = valid_response.json()

    missing_required = client.post(
        "/api/admin/garment-styles",
        json={"category": "dress"},
        headers=admin_headers,
    )
    assert missing_required.status_code == 422, missing_required.text

    blank_required = client.post(
        "/api/admin/garment-styles",
        json=_style_payload(name="   "),
        headers=admin_headers,
    )
    assert blank_required.status_code == 422, blank_required.text

    invalid_status = client.post(
        "/api/admin/garment-styles",
        json=_style_payload(status="visible"),
        headers=admin_headers,
    )
    assert invalid_status.status_code == 422, invalid_status.text

    invalid_query_status = client.get("/api/admin/garment-styles?status=visible", headers=admin_headers)
    assert invalid_query_status.status_code == 422, invalid_query_status.text

    duplicate_create = client.post(
        "/api/admin/garment-styles",
        json=_style_payload(name=style["name"]),
        headers=admin_headers,
    )
    assert duplicate_create.status_code == 409, duplicate_create.text

    second_response = client.post("/api/admin/garment-styles", json=_style_payload(), headers=admin_headers)
    assert second_response.status_code == 201, second_response.text
    second_style = second_response.json()

    duplicate_update = client.patch(
        f"/api/admin/garment-styles/{second_style['id']}",
        json={"name": style["name"]},
        headers=admin_headers,
    )
    assert duplicate_update.status_code == 409, duplicate_update.text

    missing_id = str(uuid4())
    assert client.get(f"/api/admin/garment-styles/{missing_id}", headers=admin_headers).status_code == 404
    assert client.patch(f"/api/admin/garment-styles/{missing_id}", json={"name": "missing"}, headers=admin_headers).status_code == 404
    assert client.delete(f"/api/admin/garment-styles/{missing_id}", headers=admin_headers).status_code == 404


def test_public_catalog_stays_public_and_does_not_expose_sensitive_fields(client: TestClient) -> None:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"PUBLIC-{uuid4().hex[:10]}",
            name="Public fabric",
            category="cotton",
            price_per_meter=1000,
            stock_status="in_stock",
            description_for_gpt="Публичная тестовая ткань.",
            status="published",
        )
        style = GarmentStyle(
            name=f"Public style {uuid4().hex[:8]}",
            category="dress",
            description="Публичный тестовый фасон.",
            status="published",
        )
        db.add_all([fabric, style])
        db.flush()
        _add_ready_fabric_images(db, fabric)
        db.commit()
        db.refresh(fabric)
        db.refresh(style)
        fabric_id = str(fabric.id)
        style_id = str(style.id)

    fabrics_response = client.get("/api/catalog/fabrics")
    assert fabrics_response.status_code == 200, fabrics_response.text
    fabric_item = next(item for item in fabrics_response.json()["items"] if item["id"] == fabric_id)
    assert {"password_hash", "JWT_SECRET", "BOT_INTERNAL_TOKEN", "INITIAL_ADMIN_PASSWORD"}.isdisjoint(fabric_item)

    fabric_detail = client.get(f"/api/catalog/fabrics/{fabric_id}")
    assert fabric_detail.status_code == 200, fabric_detail.text
    assert {"password_hash", "JWT_SECRET", "BOT_INTERNAL_TOKEN", "INITIAL_ADMIN_PASSWORD"}.isdisjoint(
        fabric_detail.json()
    )

    styles_response = client.get("/api/catalog/garment-styles")
    assert styles_response.status_code == 200, styles_response.text
    style_item = next(item for item in styles_response.json()["items"] if item["id"] == style_id)
    assert {"password_hash", "JWT_SECRET", "BOT_INTERNAL_TOKEN", "INITIAL_ADMIN_PASSWORD"}.isdisjoint(style_item)
