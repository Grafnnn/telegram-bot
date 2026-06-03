"""API test for the main admin fabric workflow."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xde\xa6\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_png(client: TestClient, fabric_id: str, image_type: str, sort_order: int, headers: dict[str, str]) -> dict:
    response = client.post(
        f"/api/admin/fabrics/{fabric_id}/images",
        data={"image_type": image_type, "sort_order": str(sort_order)},
        files={"file": (f"{image_type}.png", PNG_1X1, "image/png")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["image_type"] == image_type
    assert payload["image_url"].startswith("/uploads/")
    return payload


def test_admin_can_create_upload_publish_fabric_and_see_it_in_public_catalog(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert login_response.status_code == 200, login_response.text
    access_token = login_response.json()["access_token"]
    headers = _auth_headers(access_token)

    fabric_payload = {
        "sku": f"TEST-{uuid4().hex[:8]}",
        "name": "Тестовая ткань",
        "category": "cotton",
        "price_per_meter": 1000,
        "currency": "RUB",
        "stock_status": "in_stock",
        "description_for_gpt": "Тестовое описание ткани для GPT",
        "season": ["лето"],
        "recommended_for": ["платье"],
        "tags": ["тест"],
    }
    create_response = client.post("/api/admin/fabrics", json=fabric_payload, headers=headers)
    assert create_response.status_code == 201, create_response.text
    created_fabric = create_response.json()
    fabric_id = created_fabric["id"]
    assert created_fabric["status"] == "draft"

    check_before_response = client.post(
        "/api/admin/fabrics/ai/check-card",
        json={"fabric_data": created_fabric},
        headers=headers,
    )
    assert check_before_response.status_code == 200, check_before_response.text
    check_before = check_before_response.json()
    assert check_before["is_ready"] is False
    assert {"main image", "texture image"}.issubset(set(check_before["missing_fields"]))

    main_image = _upload_png(client, fabric_id, "main", 0, headers)
    texture_image = _upload_png(client, fabric_id, "texture", 1, headers)
    assert main_image["fabric_id"] == fabric_id
    assert texture_image["fabric_id"] == fabric_id

    detail_response = client.get(f"/api/admin/fabrics/{fabric_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    fabric_detail = detail_response.json()
    image_types = {image["image_type"] for image in fabric_detail["images"]}
    assert {"main", "texture"}.issubset(image_types)

    check_after_response = client.post(
        "/api/admin/fabrics/ai/check-card",
        json={"fabric_data": fabric_detail},
        headers=headers,
    )
    assert check_after_response.status_code == 200, check_after_response.text
    assert check_after_response.json()["is_ready"] is True

    publish_response = client.post(f"/api/admin/fabrics/{fabric_id}/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    assert publish_response.json()["status"] == "published"

    draft_response = client.post(
        "/api/admin/fabrics",
        json={**fabric_payload, "sku": f"DRAFT-{uuid4().hex[:8]}", "name": "Черновик ткани"},
        headers=headers,
    )
    assert draft_response.status_code == 201, draft_response.text
    draft_id = draft_response.json()["id"]

    catalog_response = client.get("/api/catalog/fabrics")
    assert catalog_response.status_code == 200, catalog_response.text
    catalog_payload = catalog_response.json()
    catalog_items = catalog_payload["items"] if isinstance(catalog_payload, dict) else catalog_payload
    catalog_ids = {item["id"] for item in catalog_items}
    assert fabric_id in catalog_ids
    assert draft_id not in catalog_ids
