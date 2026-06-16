"""API test for the main admin fabric workflow."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings


def _png_bytes(size: tuple[int, int] = (1, 1), color: tuple[int, int, int] = (20, 120, 180)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_1X1 = _png_bytes()


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

    readiness_response = client.get(f"/api/admin/fabrics/{fabric_id}/image-readiness", headers=headers)
    assert readiness_response.status_code == 200, readiness_response.text
    readiness = readiness_response.json()
    assert readiness["has_main_image_record"] is True
    assert readiness["has_texture_image_record"] is True
    assert readiness["main_file_ready"] is True
    assert readiness["texture_file_ready"] is True
    assert readiness["public_catalog_ready"] is True
    assert readiness["ai_reference_ready"] is False
    assert readiness["try_on_ready"] is False
    assert readiness["missing_required_image_types"] == []
    assert readiness["missing_upload_files"] == []
    assert "main:tiny_image" in readiness["readiness_errors"]
    assert "texture:tiny_image" in readiness["readiness_errors"]

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

    recommend_response = client.post(
        "/api/catalog/fabrics/recommend",
        json={
            "user_text": "Мне нужна ткань для летнего платья на свадьбу, чтобы выглядело дорого, но не ярко",
            "limit": 3,
        },
    )
    assert recommend_response.status_code == 200, recommend_response.text
    recommendation_payload = recommend_response.json()
    recommendation_ids = {item["fabric_id"] for item in recommendation_payload["items"]}
    assert fabric_id in recommendation_ids
    assert draft_id not in recommendation_ids
    assert recommendation_payload["preferences"]["garment_type"] == "летнее платье"
    assert recommendation_payload["preferences"]["season"] == "лето"
    assert all(item["reason"] for item in recommendation_payload["items"])


def test_publish_rejects_image_records_with_missing_upload_files(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert login_response.status_code == 200, login_response.text
    headers = _auth_headers(login_response.json()["access_token"])

    create_response = client.post(
        "/api/admin/fabrics",
        json={
            "sku": f"MISSING-FILE-{uuid4().hex[:8]}",
            "name": "Ткань с потерянным файлом",
            "category": "cotton",
            "price_per_meter": 1000,
            "currency": "RUB",
            "stock_status": "in_stock",
            "description_for_gpt": "Тестовое описание ткани для GPT",
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    fabric_id = create_response.json()["id"]
    main_image = _upload_png(client, fabric_id, "main", 0, headers)
    _upload_png(client, fabric_id, "texture", 1, headers)

    main_path = get_settings().upload_dir / main_image["image_url"].removeprefix("/uploads/")
    main_path.unlink()

    publish_response = client.post(f"/api/admin/fabrics/{fabric_id}/publish", headers=headers)

    assert publish_response.status_code == 400, publish_response.text
    assert "файл главного фото" in publish_response.json()["detail"]


def test_public_catalog_filters_legacy_published_fabric_with_missing_upload_file(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert login_response.status_code == 200, login_response.text
    headers = _auth_headers(login_response.json()["access_token"])

    valid_response = client.post(
        "/api/admin/fabrics",
        json={
            "sku": f"READY-{uuid4().hex[:8]}",
            "name": "Готовая ткань",
            "category": "cotton",
            "price_per_meter": 1000,
            "currency": "RUB",
            "stock_status": "in_stock",
            "description_for_gpt": "Тестовое описание ткани для GPT",
        },
        headers=headers,
    )
    assert valid_response.status_code == 201, valid_response.text
    valid_id = valid_response.json()["id"]
    _upload_png(client, valid_id, "main", 0, headers)
    _upload_png(client, valid_id, "texture", 1, headers)
    publish_valid = client.post(f"/api/admin/fabrics/{valid_id}/publish", headers=headers)
    assert publish_valid.status_code == 200, publish_valid.text

    broken_response = client.post(
        "/api/admin/fabrics",
        json={
            "sku": f"BROKEN-{uuid4().hex[:8]}",
            "name": "Сломанная опубликованная ткань",
            "category": "silk",
            "price_per_meter": 1200,
            "currency": "RUB",
            "stock_status": "preorder",
            "description_for_gpt": "Тестовое описание ткани для GPT",
        },
        headers=headers,
    )
    assert broken_response.status_code == 201, broken_response.text
    broken_id = broken_response.json()["id"]
    _upload_png(client, broken_id, "main", 0, headers)
    texture_image = _upload_png(client, broken_id, "texture", 1, headers)
    publish_broken = client.post(f"/api/admin/fabrics/{broken_id}/publish", headers=headers)
    assert publish_broken.status_code == 200, publish_broken.text

    texture_path = get_settings().upload_dir / texture_image["image_url"].removeprefix("/uploads/")
    texture_path.unlink()

    broken_main_response = client.post(
        "/api/admin/fabrics",
        json={
            "sku": f"BROKEN-MAIN-{uuid4().hex[:8]}",
            "name": "Сломанная ткань без файла главного фото",
            "category": "linen",
            "price_per_meter": 1300,
            "currency": "RUB",
            "stock_status": "preorder",
            "description_for_gpt": "Тестовое описание ткани для GPT",
        },
        headers=headers,
    )
    assert broken_main_response.status_code == 201, broken_main_response.text
    broken_main_id = broken_main_response.json()["id"]
    main_image = _upload_png(client, broken_main_id, "main", 0, headers)
    _upload_png(client, broken_main_id, "texture", 1, headers)
    publish_broken_main = client.post(f"/api/admin/fabrics/{broken_main_id}/publish", headers=headers)
    assert publish_broken_main.status_code == 200, publish_broken_main.text

    main_path = get_settings().upload_dir / main_image["image_url"].removeprefix("/uploads/")
    main_path.unlink()

    catalog_response = client.get("/api/catalog/fabrics")
    assert catalog_response.status_code == 200, catalog_response.text
    catalog_payload = catalog_response.json()
    catalog_ids = {item["id"] for item in catalog_payload["items"]}
    assert catalog_payload["total"] == 1
    assert valid_id in catalog_ids
    assert broken_id not in catalog_ids
    assert broken_main_id not in catalog_ids
    assert str(get_settings().upload_dir) not in catalog_response.text

    public_detail_response = client.get(f"/api/catalog/fabrics/{broken_id}")
    assert public_detail_response.status_code == 404, public_detail_response.text
    assert str(get_settings().upload_dir) not in public_detail_response.text

    public_main_detail_response = client.get(f"/api/catalog/fabrics/{broken_main_id}")
    assert public_main_detail_response.status_code == 404, public_main_detail_response.text

    admin_detail_response = client.get(f"/api/admin/fabrics/{broken_id}", headers=headers)
    assert admin_detail_response.status_code == 200, admin_detail_response.text
    readiness = admin_detail_response.json()["readiness"]
    assert readiness["public_catalog_ready"] is False
    assert readiness["missing_required_image_types"] == []
    assert readiness["missing_upload_files"][0]["image_type"] == "texture"
    assert readiness["missing_upload_files"][0]["error_code"] == "missing_file"
    assert str(get_settings().upload_dir) not in admin_detail_response.text

    hide_response = client.post(f"/api/admin/fabrics/{broken_id}/hide", headers=headers)
    assert hide_response.status_code == 200, hide_response.text
    assert hide_response.json()["status"] == "hidden"


def test_publish_rejects_missing_texture_file_and_still_allows_hide(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert login_response.status_code == 200, login_response.text
    headers = _auth_headers(login_response.json()["access_token"])

    create_response = client.post(
        "/api/admin/fabrics",
        json={
            "sku": f"MISSING-TEXTURE-{uuid4().hex[:8]}",
            "name": "Ткань без файла фактуры",
            "category": "cotton",
            "price_per_meter": 1000,
            "currency": "RUB",
            "stock_status": "in_stock",
            "description_for_gpt": "Тестовое описание ткани для GPT",
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    fabric_id = create_response.json()["id"]
    _upload_png(client, fabric_id, "main", 0, headers)
    texture_image = _upload_png(client, fabric_id, "texture", 1, headers)

    texture_path = get_settings().upload_dir / texture_image["image_url"].removeprefix("/uploads/")
    texture_path.unlink()

    publish_response = client.post(f"/api/admin/fabrics/{fabric_id}/publish", headers=headers)
    assert publish_response.status_code == 400, publish_response.text
    assert "файл фото фактуры" in publish_response.json()["detail"]
    assert str(get_settings().upload_dir) not in publish_response.text

    hide_response = client.post(f"/api/admin/fabrics/{fabric_id}/hide", headers=headers)
    assert hide_response.status_code == 200, hide_response.text
    assert hide_response.json()["status"] == "hidden"
