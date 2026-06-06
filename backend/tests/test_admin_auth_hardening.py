"""Admin authentication and role hardening tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import InsecureAdminAuthConfigError, Settings
from app.database import SessionLocal
from app.models import Admin
from app.utils.security import hash_password


def _login(client: TestClient, email: str = "admin@example.com", password: str = "admin12345") -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_admin(email: str, password: str, role: str = "admin", is_active: bool = True) -> None:
    with SessionLocal() as db:
        db.add(
            Admin(
                email=email,
                password_hash=hash_password(password),
                full_name="Test Admin",
                role=role,
                is_active=is_active,
            )
        )
        db.commit()


def test_admin_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/admin/fabrics")

    assert response.status_code == 401, response.text


def test_admin_login_rejects_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )

    assert response.status_code == 401, response.text


def test_admin_route_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/api/admin/fabrics", headers=_auth_headers("wrong"))

    assert response.status_code == 401, response.text


def test_admin_route_allows_authenticated_admin(client: TestClient) -> None:
    token = _login(client)

    response = client.get("/api/admin/fabrics", headers=_auth_headers(token))

    assert response.status_code == 200, response.text


def test_admin_route_rejects_non_admin_role(client: TestClient) -> None:
    email = f"viewer-{uuid4().hex[:8]}@example.com"
    _create_admin(email, "viewer-password", role="viewer")
    token = _login(client, email=email, password="viewer-password")

    response = client.get("/api/admin/fabrics", headers=_auth_headers(token))

    assert response.status_code == 403, response.text


def test_public_catalog_route_stays_public(client: TestClient) -> None:
    response = client.get("/api/catalog/fabrics")

    assert response.status_code == 200, response.text


def test_frontend_env_does_not_expose_admin_secrets() -> None:
    env_file = Path(__file__).resolve().parents[2] / ".env.example"
    frontend_dir = Path(__file__).resolve().parents[2] / "admin-frontend" / "src"
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in frontend_dir.rglob("*")
        if path.is_file()
    )

    assert "VITE_JWT_SECRET" not in env_file.read_text(encoding="utf-8")
    assert "INITIAL_ADMIN_PASSWORD" not in frontend_text
    assert "JWT_SECRET" not in frontend_text
    assert "admin12345" not in frontend_text


@pytest.mark.parametrize(
    ("jwt_secret", "initial_admin_password"),
    [
        ("", "strong-password"),
        ("change_me", "strong-password"),
        ("strong-secret", ""),
        ("strong-secret", "admin12345"),
    ],
)
def test_production_like_config_rejects_insecure_admin_settings(
    jwt_secret: str,
    initial_admin_password: str,
) -> None:
    settings = Settings(
        app_env="production",
        jwt_secret=jwt_secret,
        initial_admin_password=initial_admin_password,
        bot_internal_token="strong-bot-token",
    )

    with pytest.raises(InsecureAdminAuthConfigError):
        settings.validate_admin_auth_config()


def test_development_config_allows_demo_admin_settings() -> None:
    settings = Settings(app_env="development", jwt_secret="change_me", initial_admin_password="admin12345")

    settings.validate_admin_auth_config()
