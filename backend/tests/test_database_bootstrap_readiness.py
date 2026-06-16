"""Database bootstrap and migration readiness tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from app.config import InsecureAdminAuthConfigError, InsecureBootstrapConfigError, Settings
from app.database import SessionLocal
from app.models import Admin, Fabric, GarmentStyle
from app.services import bootstrap_service
from app.services.auth_service import ensure_initial_admin
from app.services.seed_service import DEMO_FABRIC_SKU, DEMO_STYLE_NAME, seed_demo_data
from app.utils.redaction import safe_exception_summary
from tests.database_guard import assert_safe_test_database

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _count_admins(email: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Admin).where(Admin.email == email)) or 0


def test_initial_admin_bootstrap_is_idempotent(client) -> None:
    email = "admin@example.com"

    with SessionLocal() as db:
        first = ensure_initial_admin(db, email, "admin12345")
        second = ensure_initial_admin(db, email, "different-password")

    assert first.id == second.id
    assert _count_admins(email) == 1


def test_demo_seed_is_idempotent(client) -> None:
    with SessionLocal() as db:
        seed_demo_data(db)
        seed_demo_data(db)
        fabric_count = db.scalar(select(func.count()).select_from(Fabric).where(Fabric.sku == DEMO_FABRIC_SKU))
        style_count = db.scalar(
            select(func.count()).select_from(GarmentStyle).where(GarmentStyle.name == DEMO_STYLE_NAME)
        )

    assert fabric_count == 1
    assert style_count == 1


def test_production_placeholders_rejected_before_admin_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_seed(*_args, **_kwargs) -> None:
        raise AssertionError("admin seed should not run with insecure production settings")

    monkeypatch.setattr(bootstrap_service, "seed_initial_admin", fail_seed)
    settings = Settings(
        app_env="production",
        jwt_secret="change_me",
        initial_admin_password="admin12345",
        bot_internal_token="strong-bot-token",
    )

    with pytest.raises(InsecureAdminAuthConfigError):
        bootstrap_service.bootstrap_database(object(), settings)  # type: ignore[arg-type]


def test_production_rejects_demo_seed_before_admin_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_seed(*_args, **_kwargs) -> None:
        raise AssertionError("admin seed should not run when demo seed is enabled in production")

    monkeypatch.setattr(bootstrap_service, "seed_initial_admin", fail_seed)
    settings = Settings(
        app_env="production",
        jwt_secret="strong-secret",
        initial_admin_password="strong-password",
        bot_internal_token="strong-bot-token",
        seed_demo_data=True,
    )

    with pytest.raises(InsecureBootstrapConfigError):
        bootstrap_service.bootstrap_database(object(), settings)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://postgres:postgres@localhost:5432/fashion_bot",
        "sqlite:///tmp/fashion_bot_test.db",
    ],
)
def test_test_database_guard_rejects_unsafe_urls(database_url: str) -> None:
    with pytest.raises(RuntimeError):
        assert_safe_test_database(database_url)


def test_test_database_guard_accepts_postgres_test_database() -> None:
    assert_safe_test_database("postgresql+psycopg://postgres:postgres@localhost:5432/fashion_bot_test")


def test_bootstrap_error_summary_redacts_database_credentials() -> None:
    summary = safe_exception_summary(
        RuntimeError(
            "could not connect to postgresql+psycopg://postgres:db-secret@db:5432/fashion_bot "
            "password=db-secret bot_internal_token=runtime-secret"
        )
    )

    assert "db-secret" not in summary
    assert "runtime-secret" not in summary
    assert "postgres:[REDACTED]@db" in summary
    assert "password=[REDACTED]" in summary
    assert "bot_internal_token=[REDACTED]" in summary


def test_alembic_has_single_expected_head() -> None:
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(alembic_config)

    assert script.get_heads() == ["0002_generation_mask_url"]
