"""Shared query parameter constraints for API list endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Query

from app.schemas.common import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT

PageQuery = Annotated[int, Query(ge=1)]
LimitQuery = Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)]
TextSearchQuery = Annotated[str | None, Query(min_length=1, max_length=255)]
ShortTextFilterQuery = Annotated[str | None, Query(min_length=1, max_length=120)]
NonNegativeDecimalQuery = Annotated[Decimal | None, Query(ge=0)]
CreatedAtSort = Literal["created_at", "-created_at"]
CreatedAtSortQuery = Annotated[CreatedAtSort, Query()]


def apply_created_at_sort(stmt, model, sort: CreatedAtSort):
    created_at = getattr(model, "created_at")
    return stmt.order_by(created_at.asc() if sort == "created_at" else created_at.desc())


__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "CreatedAtSort",
    "CreatedAtSortQuery",
    "LimitQuery",
    "NonNegativeDecimalQuery",
    "PageQuery",
    "ShortTextFilterQuery",
    "TextSearchQuery",
    "apply_created_at_sort",
]
