"""Pytest fixtures for backend API tests."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fashion_bot_test"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_TEST_DATABASE_URL

os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("UPLOAD_DIR", "/tmp/fashion-bot-uploads")
os.environ.setdefault("OPENAI_API_KEY", "put_openai_key_here")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "put_token_here")
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "admin12345")
os.environ.setdefault("SEED_DEMO_DATA", "false")

from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed_service import seed_initial_admin  # noqa: E402


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _assert_safe_test_database(database_url: str) -> None:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        raise RuntimeError("Backend tests require PostgreSQL because migrations use PostgreSQL-specific types.")
    if "test" not in (url.database or "").lower():
        raise RuntimeError("Refusing to run backend tests against a database whose name does not contain 'test'.")


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Apply migrations to the configured PostgreSQL test database before tests run."""

    _assert_safe_test_database(TEST_DATABASE_URL)
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_config, "head")


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient with a seeded initial admin and isolated upload folders."""

    get_settings.cache_clear()
    settings = get_settings()
    shutil.rmtree(settings.upload_dir, ignore_errors=True)
    for folder in ["fabrics", "garment-styles", "generations", "user-photos"]:
        Path(settings.upload_dir, folder).mkdir(parents=True, exist_ok=True)

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    with SessionLocal() as db:
        seed_initial_admin(db, settings.initial_admin_email, settings.initial_admin_password)

    with TestClient(app) as test_client:
        yield test_client
