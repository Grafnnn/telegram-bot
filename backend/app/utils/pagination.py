"""Pagination utilities."""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import DEFAULT_PAGE, MAX_PAGE_LIMIT


def paginate(db: Session, stmt: Select, page: int, limit: int) -> tuple[list, int]:
    page = max(page, DEFAULT_PAGE)
    limit = min(max(limit, 1), MAX_PAGE_LIMIT)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(db.scalars(stmt.offset((page - 1) * limit).limit(limit)).unique())
    return items, total
