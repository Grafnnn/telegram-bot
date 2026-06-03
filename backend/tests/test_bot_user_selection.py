from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Fabric, FabricImage


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.app.state.testing_session_local = TestingSessionLocal
        yield test_client
    app.dependency_overrides.clear()


def create_fabric(client: TestClient, status: str, name: str) -> str:
    db = client.app.state.testing_session_local()
    try:
        fabric = Fabric(
            name=name,
            category="Плательные",
            color="Пастельный",
            price="1200 ₽/м",
            availability="В наличии",
            short_description="Легкая ткань для нарядных вещей.",
            status=status,
        )
        fabric.images.append(FabricImage(image_url="/uploads/fabrics/main.jpg", is_main=True, sort_order=0))
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        return fabric.id
    finally:
        db.close()


def test_upsert_select_and_get_selected_published_fabric(client: TestClient) -> None:
    fabric_id = create_fabric(client, "published", "Шелк пастельный")

    upsert_response = client.post(
        "/api/bot/users/upsert",
        json={
            "telegram_id": 123456,
            "username": "username",
            "first_name": "Имя",
            "last_name": "Фамилия",
        },
    )

    assert upsert_response.status_code == 200
    user_payload = upsert_response.json()
    assert user_payload["telegram_id"] == 123456
    assert user_payload["selected_fabric_id"] is None
    assert user_payload["selected_garment_style_id"] is None

    select_response = client.post(
        "/api/bot/users/123456/selected-fabric",
        json={"fabric_id": fabric_id},
    )

    assert select_response.status_code == 200
    selected_payload = select_response.json()
    assert selected_payload["selected"] is True
    assert selected_payload["fabric"]["id"] == fabric_id
    assert selected_payload["fabric"]["images"][0]["image_url"] == "/uploads/fabrics/main.jpg"

    get_response = client.get("/api/bot/users/123456/selected-fabric")

    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["selected"] is True
    assert get_payload["fabric"]["id"] == fabric_id


def test_get_selected_fabric_returns_clear_empty_state(client: TestClient) -> None:
    response = client.get("/api/bot/users/999/selected-fabric")

    assert response.status_code == 200
    assert response.json() == {"selected": False, "message": "Вы пока не выбрали ткань.", "fabric": None}


@pytest.mark.parametrize("status", ["draft", "hidden", "archived"])
def test_cannot_select_unpublished_fabric(client: TestClient, status: str) -> None:
    fabric_id = create_fabric(client, status, "Неопубликованная ткань")

    response = client.post("/api/bot/users/123456/selected-fabric", json={"fabric_id": fabric_id})

    assert response.status_code == 403
    assert response.json()["detail"] == "Only published fabrics can be selected"


def test_cannot_select_missing_fabric(client: TestClient) -> None:
    response = client.post(
        "/api/bot/users/123456/selected-fabric",
        json={"fabric_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Fabric not found"
