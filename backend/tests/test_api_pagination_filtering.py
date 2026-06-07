"""API pagination and filtering hardening tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Fabric, Generation
from app.models.garment_style import GarmentStyle

SENSITIVE_FIELD_NAMES = {"password_hash", "JWT_SECRET", "BOT_INTERNAL_TOKEN", "INITIAL_ADMIN_PASSWORD", "OPENAI_API_KEY"}


def _login(client: TestClient, email: str = "admin@example.com", password: str = "admin12345") -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_page_shape(payload: dict, *, page: int = 1, limit: int = 20) -> None:
    assert set(payload) == {"items", "total", "page", "limit"}
    assert isinstance(payload["items"], list)
    assert isinstance(payload["total"], int)
    assert payload["page"] == page
    assert payload["limit"] == limit


def _seed_catalog_rows() -> tuple[str, str]:
    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"PAGE-{uuid4().hex[:10]}",
            name="Pagination fabric",
            category="cotton",
            color="blue",
            price_per_meter=1000,
            stock_status="in_stock",
            description_for_gpt="Test fabric for pagination hardening.",
            status="published",
        )
        style = GarmentStyle(
            name=f"Pagination style {uuid4().hex[:8]}",
            category="dress",
            description="Test style for pagination hardening.",
            status="published",
        )
        generation = Generation(mode="catalog_style", status="failed", error_message="safe failure")
        db.add_all([fabric, style, generation])
        db.commit()
        db.refresh(fabric)
        db.refresh(style)
        return str(fabric.id), str(style.id)


def test_public_catalog_list_pagination_filtering_and_response_shape(client: TestClient) -> None:
    fabric_id, style_id = _seed_catalog_rows()

    fabrics_response = client.get("/api/catalog/fabrics")
    assert fabrics_response.status_code == 200, fabrics_response.text
    fabrics_page = fabrics_response.json()
    _assert_page_shape(fabrics_page)
    fabric_item = next(item for item in fabrics_page["items"] if item["id"] == fabric_id)
    assert SENSITIVE_FIELD_NAMES.isdisjoint(fabric_item)

    styles_response = client.get("/api/catalog/garment-styles")
    assert styles_response.status_code == 200, styles_response.text
    styles_page = styles_response.json()
    _assert_page_shape(styles_page)
    assert any(item["id"] == style_id for item in styles_page["items"])

    empty_response = client.get(f"/api/catalog/fabrics?search=no-such-fabric-{uuid4().hex}")
    assert empty_response.status_code == 200, empty_response.text
    _assert_page_shape(empty_response.json())
    assert empty_response.json()["items"] == []

    for query in ["page=0", "page=-1", "limit=0", "limit=-1", "limit=101", "sort=sku", "min_price=-1"]:
        invalid_response = client.get(f"/api/catalog/fabrics?{query}")
        assert invalid_response.status_code == 422, invalid_response.text

    invalid_price_range = client.get("/api/catalog/fabrics?min_price=200&max_price=100")
    assert invalid_price_range.status_code == 422, invalid_price_range.text


def test_admin_catalog_and_generation_lists_validate_queries_and_auth(client: TestClient) -> None:
    _seed_catalog_rows()
    admin_headers = _auth_headers(_login(client))

    assert client.get("/api/admin/fabrics").status_code == 401
    assert client.get("/api/admin/garment-styles").status_code == 401
    assert client.get("/api/admin/generations").status_code == 401

    fabrics_response = client.get("/api/admin/fabrics?limit=1", headers=admin_headers)
    assert fabrics_response.status_code == 200, fabrics_response.text
    _assert_page_shape(fabrics_response.json(), limit=1)

    styles_response = client.get("/api/admin/garment-styles", headers=admin_headers)
    assert styles_response.status_code == 200, styles_response.text
    _assert_page_shape(styles_response.json())

    generations_response = client.get("/api/admin/generations?status=failed", headers=admin_headers)
    assert generations_response.status_code == 200, generations_response.text
    _assert_page_shape(generations_response.json())

    invalid_queries = {
        "/api/admin/fabrics": ["page=0", "limit=101", "sort=sku", "status=published-ish", "stock_status=available"],
        "/api/admin/garment-styles": ["page=-1", "limit=0", "limit=101", "sort=name", "status=visible"],
        "/api/admin/generations": ["page=0", "limit=101", "sort=status", "status=stuck"],
    }
    for path, queries in invalid_queries.items():
        for query in queries:
            response = client.get(f"{path}?{query}", headers=admin_headers)
            assert response.status_code == 422, response.text
