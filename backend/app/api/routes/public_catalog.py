"""Public catalog routes for the Telegram bot."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Fabric, GarmentStyle
from app.schemas.common import PaginatedResponse
from app.schemas.fabric import FabricRead, FabricRecommendRequest, FabricRecommendResponse
from app.schemas.garment_style import GarmentStyleRead
from app.services.fabric_recommendation_service import build_fabric_recommendations
from app.services.openai_service import extract_fabric_preferences
from app.utils.pagination import paginate

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _published_fabric_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id, Fabric.status == "published"))
    if fabric is None:
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
    candidates = list(db.scalars(stmt).unique())
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
def list_public_fabrics(search: str | None = None, category: str | None = None, color: str | None = None, pattern: str | None = None, density: str | None = None, season: str | None = None, recommended_for: str | None = None, min_price: Decimal | None = None, max_price: Decimal | None = None, page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    stmt = select(Fabric).options(selectinload(Fabric.images)).where(Fabric.status == "published").order_by(Fabric.created_at.desc())
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
    items, total = paginate(db, stmt, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/fabrics/{fabric_id}", response_model=FabricRead)
def get_public_fabric(fabric_id: UUID, db: Session = Depends(get_db)) -> Fabric:
    return _published_fabric_or_404(db, fabric_id)


@router.get("/garment-styles", response_model=PaginatedResponse[GarmentStyleRead])
def list_public_styles(page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    stmt = select(GarmentStyle).where(GarmentStyle.status == "published").order_by(GarmentStyle.created_at.desc())
    items, total = paginate(db, stmt, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/garment-styles/{style_id}", response_model=GarmentStyleRead)
def get_public_style(style_id: UUID, db: Session = Depends(get_db)) -> GarmentStyle:
    style = db.scalar(select(GarmentStyle).where(GarmentStyle.id == style_id, GarmentStyle.status == "published"))
    if style is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фасон не найден")
    return style
