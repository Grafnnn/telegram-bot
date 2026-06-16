"""Public catalog routes for the Telegram bot."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.query_params import (
    DEFAULT_PAGE_LIMIT,
    CreatedAtSortQuery,
    LimitQuery,
    NonNegativeDecimalQuery,
    PageQuery,
    ShortTextFilterQuery,
    TextSearchQuery,
    apply_created_at_sort,
)
from app.database import get_db
from app.models import Fabric, GarmentStyle
from app.schemas.common import PaginatedResponse
from app.schemas.fabric import FabricRead, FabricRecommendRequest, FabricRecommendResponse
from app.schemas.garment_style import GarmentStyleRead
from app.services.fabric_recommendation_service import build_fabric_recommendations
from app.services.image_readiness_service import fabric_image_readiness_report
from app.services.openai_service import extract_fabric_preferences
from app.utils.pagination import paginate

router = APIRouter(prefix="/catalog", tags=["catalog"])
logger = logging.getLogger(__name__)


def _public_catalog_ready_fabrics(fabrics: list[Fabric]) -> list[Fabric]:
    ready_fabrics = []
    for fabric in fabrics:
        readiness = fabric_image_readiness_report(fabric)
        if readiness.public_catalog_ready:
            ready_fabrics.append(fabric)
            continue
        missing_types = sorted(set(readiness.missing_required_image_types))
        missing_files = sorted({item.image_type or "image" for item in readiness.missing_upload_files})
        logger.warning(
            "Skipping public fabric with missing required upload image fabric_id=%s sku=%s missing_types=%s missing_files=%s",
            fabric.id,
            fabric.sku,
            ",".join(missing_types) or "-",
            ",".join(missing_files) or "-",
        )
    return ready_fabrics


def _public_catalog_page(fabrics: list[Fabric], page: int, limit: int) -> tuple[list[Fabric], int]:
    ready_fabrics = _public_catalog_ready_fabrics(fabrics)
    start = (page - 1) * limit
    end = start + limit
    return ready_fabrics[start:end], len(ready_fabrics)


def _published_fabric_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id, Fabric.status == "published"))
    if fabric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    if not _public_catalog_ready_fabrics([fabric]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    return fabric


@router.post("/fabrics/recommend", response_model=FabricRecommendResponse)
def recommend_fabrics(payload: FabricRecommendRequest, db: Session = Depends(get_db)):
    stmt = (
        select(Fabric)
        .options(selectinload(Fabric.images))
        .where(Fabric.status == "published")
        .order_by(Fabric.created_at.desc())
        .limit(max(payload.limit * 10, 50))
    )
    candidates = _public_catalog_ready_fabrics(list(db.scalars(stmt).unique()))
    preferred_stock_candidates = [fabric for fabric in candidates if fabric.stock_status in {"in_stock", "preorder"}]
    recommendation_candidates = preferred_stock_candidates or candidates
    preferences_result = extract_fabric_preferences(payload.user_text)
    preferences = preferences_result.get("preferences", {})
    recommendations = build_fabric_recommendations(preferences, recommendation_candidates, payload.limit)
    return {
        "preferences": preferences,
        "items": recommendations,
        "ai": {"ok": preferences_result.get("ok", False), "error": preferences_result.get("error")},
    }


@router.get("/fabrics", response_model=PaginatedResponse[FabricRead])
def list_public_fabrics(
    search: TextSearchQuery = None,
    category: ShortTextFilterQuery = None,
    color: ShortTextFilterQuery = None,
    pattern: ShortTextFilterQuery = None,
    density: ShortTextFilterQuery = None,
    season: ShortTextFilterQuery = None,
    recommended_for: ShortTextFilterQuery = None,
    min_price: NonNegativeDecimalQuery = None,
    max_price: NonNegativeDecimalQuery = None,
    page: PageQuery = 1,
    limit: LimitQuery = DEFAULT_PAGE_LIMIT,
    sort: CreatedAtSortQuery = "-created_at",
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "min_price должен быть меньше или равен max_price")
    stmt = select(Fabric).options(selectinload(Fabric.images)).where(Fabric.status == "published")
    stmt = apply_created_at_sort(stmt, Fabric, sort)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Fabric.sku.ilike(like), Fabric.name.ilike(like), Fabric.category.ilike(like), Fabric.description_for_gpt.ilike(like)))
    if category:
        stmt = stmt.where(Fabric.category == category)
    if color:
        stmt = stmt.where(Fabric.color == color)
    if pattern:
        stmt = stmt.where(Fabric.pattern == pattern)
    if density:
        stmt = stmt.where(Fabric.density == density)
    if season:
        stmt = stmt.where(Fabric.season.contains([season]))
    if recommended_for:
        stmt = stmt.where(Fabric.recommended_for.contains([recommended_for]))
    if min_price is not None:
        stmt = stmt.where(Fabric.price_per_meter >= min_price)
    if max_price is not None:
        stmt = stmt.where(Fabric.price_per_meter <= max_price)
    candidates = list(db.scalars(stmt).unique())
    items, total = _public_catalog_page(candidates, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/fabrics/{fabric_id}", response_model=FabricRead)
def get_public_fabric(fabric_id: UUID, db: Session = Depends(get_db)) -> Fabric:
    return _published_fabric_or_404(db, fabric_id)


@router.get("/garment-styles", response_model=PaginatedResponse[GarmentStyleRead])
def list_public_styles(
    page: PageQuery = 1,
    limit: LimitQuery = DEFAULT_PAGE_LIMIT,
    sort: CreatedAtSortQuery = "-created_at",
    db: Session = Depends(get_db),
):
    stmt = select(GarmentStyle).where(GarmentStyle.status == "published")
    stmt = apply_created_at_sort(stmt, GarmentStyle, sort)
    items, total = paginate(db, stmt, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/garment-styles/{style_id}", response_model=GarmentStyleRead)
def get_public_style(style_id: UUID, db: Session = Depends(get_db)) -> GarmentStyle:
    style = db.scalar(select(GarmentStyle).where(GarmentStyle.id == style_id, GarmentStyle.status == "published"))
    if style is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фасон не найден")
    return style
