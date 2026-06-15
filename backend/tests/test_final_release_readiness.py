"""Final MVP release readiness guardrails."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_ci_covers_release_readiness_jobs() -> None:
    ci_text = _read(".github/workflows/ci.yml")

    required_fragments = {
        "name: Whitespace check",
        "name: Backend",
        "name: Admin frontend",
        "name: Bot",
        "name: Docker Compose config",
        "Run Alembic migrations",
        "Run backend API tests",
        "Run frontend UX tests",
        "Build frontend",
        "Run bot journey tests",
        "Validate Docker Compose configuration",
    }

    assert {fragment for fragment in required_fragments if fragment not in ci_text} == set()


def test_release_checklists_are_documented() -> None:
    readme_text = _read("README.md")

    required_fragments = {
        "## Required production environment",
        "## Deployment checklist",
        "## Post-merge smoke checks",
        "Rollback notes",
        "GitHub Actions jobs green",
        "APP_ENV=production",
        "JWT_SECRET",
        "INITIAL_ADMIN_PASSWORD",
        "BOT_INTERNAL_TOKEN",
        "VITE_API_BASE_URL",
        "VITE_BACKEND_PUBLIC_URL",
        "OPENAI_IMAGE_MODEL",
        "BOT_GENERATION_TIMEOUT_SECONDS",
        "alembic upgrade head",
        "/api/health",
        "X-Request-ID",
        "Retry-After",
        "raw backend/provider errors",
    }

    assert {fragment for fragment in required_fragments if fragment not in readme_text} == set()


def test_admin_catalog_routes_keep_admin_auth_guards() -> None:
    for relative_path in (
        "backend/app/api/routes/admin_fabrics.py",
        "backend/app/api/routes/admin_garment_styles.py",
    ):
        route_text = _read(relative_path)
        route_chunks = re.split(r"\n(?=@router\.)", route_text)
        admin_route_chunks = [chunk for chunk in route_chunks if chunk.startswith("@router.")]

        assert admin_route_chunks, f"{relative_path} should define admin routes"
        for chunk in admin_route_chunks:
            guard_region = chunk[:900]
            assert "Depends(get_current_admin)" in guard_region, chunk.splitlines()[0]


def test_public_catalog_routes_stay_public() -> None:
    public_catalog_text = _read("backend/app/api/routes/public_catalog.py")

    assert "get_current_admin" not in public_catalog_text
    assert "verify_bot_internal_token" not in public_catalog_text


def test_bot_facing_mutations_keep_token_and_abuse_guards() -> None:
    bot_users_text = _compact(_read("backend/app/api/routes/bot_users.py"))
    generations_text = _compact(_read("backend/app/api/routes/generations.py"))
    bot_client_text = _read("bot/app/api_client.py")

    assert "dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_bot_api)]" in bot_users_text
    assert (
        "dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_catalog_style_generation)]"
        in generations_text
    )
    assert (
        "dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_user_photo_generation)]"
        in generations_text
    )
    assert '"X-Bot-Token"' in bot_client_text


def test_frontend_env_boundary_does_not_expose_backend_secrets() -> None:
    env_text = _read(".env.example")
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "admin-frontend" / "src").rglob("*")
        if path.is_file()
    )
    vite_env_names = {line.split("=", 1)[0] for line in env_text.splitlines() if line.startswith("VITE_")}
    backend_secret_names = {
        "JWT_SECRET",
        "INITIAL_ADMIN_PASSWORD",
        "BOT_INTERNAL_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY",
        "POSTGRES_PASSWORD",
    }

    assert vite_env_names == {"VITE_API_BASE_URL", "VITE_BACKEND_PUBLIC_URL"}
    assert {name for name in backend_secret_names if name in frontend_text} == set()
