"""API tests for recommending only existing published fabrics."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.test_fabric_admin_workflow import PNG_1X1


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _upload_required_images(client: TestClient, fabric_id: str, headers: dict[str, str]) -> None:
    for image_type, sort_order in [("main", 0), ("texture", 1)]:
        response = client.post(
            f"/api/admin/fabrics/{fabric_id}/images",
            data={"image_type": image_type, "sort_order": str(sort_order)},
            files={"file": (f"{image_type}.png", PNG_1X1, "image/png")},
            headers=headers,
        )
        assert response.status_code == 201, response.text


def _create_fabric(client: TestClient, headers: dict[str, str], *, status: str, stock_status: str, name: str) -> str:
    response = client.post(
        "/api/admin/fabrics",
        json={
            "sku": f"REC-{uuid4().hex[:10]}",
            "name": name,
            "category": "dress",
            "composition": "вискоза и шелк",
            "color": "пудровый",
            "shade": "пастельный",
            "texture": "мягкая струящаяся фактура",
            "density": "легкая",
            "season": ["лето"],
            "recommended_for": ["летнее платье", "платье", "свадьба"],
            "price_per_meter": 1800,
            "currency": "RUB",
            "stock_status": stock_status,
            "description_for_gpt": "Легкая пастельная ткань для летнего платья на свадьбу, выглядит дорого и элегантно, хорошо драпируется.",
            "tags": ["пастельный", "легкая", "драпировка", "свадьба"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    fabric_id = response.json()["id"]
    if status in {"published", "hidden", "archived"}:
        _upload_required_images(client, fabric_id, headers)
        publish_response = client.post(f"/api/admin/fabrics/{fabric_id}/publish", headers=headers)
        assert publish_response.status_code == 200, publish_response.text
    if status == "hidden":
        hide_response = client.post(f"/api/admin/fabrics/{fabric_id}/hide", headers=headers)
        assert hide_response.status_code == 200, hide_response.text
    if status == "archived":
        archive_response = client.post(f"/api/admin/fabrics/{fabric_id}/archive", headers=headers)
        assert archive_response.status_code == 200, archive_response.text
    return fabric_id


def test_recommendations_return_only_existing_published_available_fabrics(client: TestClient) -> None:
    headers = _auth_headers(client)
    published_in_stock_id = _create_fabric(client, headers, status="published", stock_status="in_stock", name="Пудровая ткань для летнего платья")
    published_preorder_id = _create_fabric(client, headers, status="published", stock_status="preorder", name="Пастельная ткань под заказ")
    draft_id = _create_fabric(client, headers, status="draft", stock_status="in_stock", name="Черновик пастельной ткани")
    hidden_id = _create_fabric(client, headers, status="hidden", stock_status="in_stock", name="Скрытая пастельная ткань")
    archived_id = _create_fabric(client, headers, status="archived", stock_status="in_stock", name="Архивная пастельная ткань")
    out_of_stock_id = _create_fabric(client, headers, status="published", stock_status="out_of_stock", name="Нет в наличии пастельная ткань")

    response = client.post(
        "/api/catalog/fabrics/recommend",
        json={"user_text": "Нужна легкая ткань для летнего платья на свадьбу в пастельном цвете", "limit": 5},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    items = payload["items"]
    assert items

    recommended_ids = {item["fabric_id"] for item in items}
    assert published_in_stock_id in recommended_ids
    assert recommended_ids.intersection({published_in_stock_id, published_preorder_id})
    assert draft_id not in recommended_ids
    assert hidden_id not in recommended_ids
    assert archived_id not in recommended_ids
    assert out_of_stock_id not in recommended_ids

    for item in items:
        detail_response = client.get(f"/api/catalog/fabrics/{item['fabric_id']}")
        assert detail_response.status_code == 200, detail_response.text
        assert item["fabric"]["id"] == item["fabric_id"]
        assert item["reason"]
        assert "possible_issue" in item
        assert item["fabric"]["stock_status"] in {"in_stock", "preorder"}

    assert payload["preferences"]["garment_type"] == "летнее платье"
    assert payload["preferences"]["season"] == "лето"
    assert payload["ai"]["ok"] is False
