"""Pytest fixtures for backend API tests."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/fashion_bot")
os.environ.setdefault("UPLOAD_DIR", "/tmp/fashion-bot-uploads")
os.environ.setdefault("OPENAI_API_KEY", "put_openai_key_here")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "put_token_here")
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "admin12345")
os.environ.setdefault("SEED_DEMO_DATA", "false")

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed_service import seed_initial_admin  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient with a seeded initial admin and isolated upload folders."""

    get_settings.cache_clear()
    settings = get_settings()
    shutil.rmtree(settings.upload_dir, ignore_errors=True)
    for folder in ["fabrics", "garment-styles", "generations", "user-photos"]:
        Path(settings.upload_dir, folder).mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        seed_initial_admin(db, settings.initial_admin_email, settings.initial_admin_password)

    with TestClient(app) as test_client:
        yield test_client
