"""Admin fabric routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.rate_limit import rate_limit_upload
from app.api.query_params import (
    DEFAULT_PAGE_LIMIT,
    CreatedAtSortQuery,
    LimitQuery,
    PageQuery,
    ShortTextFilterQuery,
    TextSearchQuery,
    apply_created_at_sort,
)
from app.api.deps import get_current_admin
from app.database import get_db
from app.models import Admin, Fabric, FabricImage, Generation
from app.schemas.common import PaginatedResponse
from app.schemas.fabric import FabricAIRequest, FabricCreate, FabricImageRead, FabricRead, FabricStatus, FabricUpdate, StockStatus
from app.schemas.generation import GenerationRead, GenerationStatus
from app.services.openai_service import check_fabric_card, generate_admin_fabric_description
from app.services.storage_service import save_upload
from app.utils.pagination import paginate

router = APIRouter(prefix="/admin", tags=["admin"])


PUBLISH_FIELD_LABELS = {
    "sku": "артикул",
    "name": "название",
    "category": "категория",
    "price_per_meter": "цена за метр",
    "stock_status": "наличие",
    "description_for_gpt": "описание для GPT",
    "main image": "главное фото",
    "texture image": "фото фактуры",
}

ALLOWED_FABRIC_IMAGE_TYPES = {"main", "texture", "extra"}


def _fabric_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id))
    if fabric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    return fabric


def _apply_fabric_filters(stmt, search=None, category=None, color=None, status_value=None, stock_status=None):
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Fabric.sku.ilike(like), Fabric.name.ilike(like), Fabric.category.ilike(like)))
    if category:
        stmt = stmt.where(Fabric.category == category)
    if color:
        stmt = stmt.where(Fabric.color == color)
    if status_value:
        stmt = stmt.where(Fabric.status == status_value)
    if stock_status:
        stmt = stmt.where(Fabric.stock_status == stock_status)
    return stmt


def _payload_dict(payload: FabricCreate | FabricUpdate) -> dict:
    return payload.model_dump(exclude_unset=True)


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ткань с таким артикулом уже существует") from exc


@router.post("/fabrics/ai/generate-description")
def ai_generate_description(payload: FabricAIRequest, _: Admin = Depends(get_current_admin)) -> dict:
    return generate_admin_fabric_description(payload.fabric_data, payload.image_url)


@router.post("/fabrics/ai/check-card")
def ai_check_card(payload: FabricAIRequest, _: Admin = Depends(get_current_admin)) -> dict:
    return check_fabric_card(payload.fabric_data)


@router.get("/fabrics", response_model=PaginatedResponse[FabricRead])
def list_fabrics(
    search: TextSearchQuery = None,
    category: ShortTextFilterQuery = None,
    color: ShortTextFilterQuery = None,
    status: FabricStatus | None = None,
    stock_status: StockStatus | None = None,
    page: PageQuery = 1,
    limit: LimitQuery = DEFAULT_PAGE_LIMIT,
    sort: CreatedAtSortQuery = "-created_at",
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Fabric).options(selectinload(Fabric.images))
    stmt = apply_created_at_sort(stmt, Fabric, sort)
    stmt = _apply_fabric_filters(stmt, search, category, color, status, stock_status)
    items, total = paginate(db, stmt, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/fabrics", response_model=FabricRead, status_code=status.HTTP_201_CREATED)
def create_fabric(payload: FabricCreate, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> Fabric:
    fabric = Fabric(**_payload_dict(payload))
    db.add(fabric)
    _commit_or_conflict(db)
    db.refresh(fabric)
    return _fabric_or_404(db, fabric.id)


@router.get("/fabrics/{fabric_id}", response_model=FabricRead)
def get_fabric(fabric_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> Fabric:
    return _fabric_or_404(db, fabric_id)


@router.patch("/fabrics/{fabric_id}", response_model=FabricRead)
def update_fabric(fabric_id: UUID, payload: FabricUpdate, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> Fabric:
    fabric = _fabric_or_404(db, fabric_id)
    for key, value in _payload_dict(payload).items():
        setattr(fabric, key, value)
    _commit_or_conflict(db)
    return _fabric_or_404(db, fabric_id)


@router.delete("/fabrics/{fabric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fabric(fabric_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> None:
    db.delete(_fabric_or_404(db, fabric_id))
    db.commit()


def _set_status(db: Session, fabric_id: UUID, value: str) -> Fabric:
    fabric = _fabric_or_404(db, fabric_id)
    if value == "published":
        image_types = {image.image_type for image in fabric.images}
        missing = []
        for field in ["sku", "name", "category", "price_per_meter", "stock_status", "description_for_gpt"]:
            if not getattr(fabric, field):
                missing.append(field)
        if "main" not in image_types:
            missing.append("main image")
        if "texture" not in image_types:
            missing.append("texture image")
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Нельзя опубликовать ткань. Не хватает: {', '.join(PUBLISH_FIELD_LABELS.get(field, field) for field in missing)}",
            )
    fabric.status = value
    db.commit()
    return _fabric_or_404(db, fabric_id)


@router.post("/fabrics/{fabric_id}/publish", response_model=FabricRead)
def publish_fabric(fabric_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> Fabric:
    return _set_status(db, fabric_id, "published")


@router.post("/fabrics/{fabric_id}/hide", response_model=FabricRead)
def hide_fabric(fabric_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> Fabric:
    return _set_status(db, fabric_id, "hidden")


@router.post("/fabrics/{fabric_id}/archive", response_model=FabricRead)
def archive_fabric(fabric_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> Fabric:
    return _set_status(db, fabric_id, "archived")


@router.post("/fabrics/{fabric_id}/images", response_model=FabricImageRead, status_code=status.HTTP_201_CREATED)
async def upload_fabric_image(
    fabric_id: UUID,
    file: UploadFile = File(...),
    image_type: str = Form(...),
    sort_order: int = Form(0),
    _: Admin = Depends(get_current_admin),
    __: None = Depends(rate_limit_upload),
    db: Session = Depends(get_db),
) -> FabricImage:
    _fabric_or_404(db, fabric_id)
    if image_type not in ALLOWED_FABRIC_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "image_type должен быть main, texture или extra")
    if sort_order < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "sort_order должен быть неотрицательным")
    image_url = await save_upload(file, "fabrics")
    image = FabricImage(fabric_id=fabric_id, image_url=image_url, image_type=image_type, sort_order=sort_order)
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.delete("/fabrics/{fabric_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fabric_image(fabric_id: UUID, image_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> None:
    image = db.get(FabricImage, image_id)
    if image is None or image.fabric_id != fabric_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Изображение не найдено")
    db.delete(image)
    db.commit()


@router.get("/generations", response_model=PaginatedResponse[GenerationRead])
def list_generations(
    generation_status: GenerationStatus | None = Query(default=None, alias="status"),
    page: PageQuery = 1,
    limit: LimitQuery = DEFAULT_PAGE_LIMIT,
    sort: CreatedAtSortQuery = "-created_at",
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Generation)
    stmt = apply_created_at_sort(stmt, Generation, sort)
    if generation_status:
        stmt = stmt.where(Generation.status == generation_status)
    items, total = paginate(db, stmt, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}
