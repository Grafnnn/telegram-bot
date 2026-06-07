"""Shared backend test database safety guard."""

from sqlalchemy.engine import make_url


def assert_safe_test_database(database_url: str) -> None:
    """Refuse destructive backend tests outside a PostgreSQL test database."""

    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        raise RuntimeError("Backend tests require PostgreSQL because migrations use PostgreSQL-specific types.")
    if "test" not in (url.database or "").lower():
        raise RuntimeError("Refusing to run backend tests against a database whose name does not contain 'test'.")
