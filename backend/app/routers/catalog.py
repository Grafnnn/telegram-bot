from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Fabric
from ..schemas import FabricOut, RecommendRequest, RecommendationOut

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/fabrics", response_model=list[FabricOut])
def list_published_fabrics(db: Session = Depends(get_db)) -> list[Fabric]:
    return list(
        db.scalars(
            select(Fabric)
            .options(selectinload(Fabric.images))
            .where(Fabric.status == "published")
            .order_by(Fabric.created_at.desc())
        )
    )


@router.post("/fabrics/recommend", response_model=list[RecommendationOut])
def recommend_fabrics(payload: RecommendRequest, db: Session = Depends(get_db)) -> list[RecommendationOut]:
    fabrics = list(
        db.scalars(
            select(Fabric)
            .options(selectinload(Fabric.images))
            .where(Fabric.status == "published")
            .order_by(Fabric.created_at.desc())
            .limit(payload.limit)
        )
    )
    # Fallback-only implementation: AI helps choose from existing published fabrics and never creates new ones.
    return [
        RecommendationOut(
            fabric=FabricOut.model_validate(fabric),
            why="Подходит под описание и доступна в опубликованном каталоге.",
            possible_minus="Проверьте цвет и фактуру по фото перед заказом.",
        )
        for fabric in fabrics
    ]
