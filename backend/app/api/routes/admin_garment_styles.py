"""Admin garment style routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.rate_limit import rate_limit_upload
from app.api.query_params import (
    DEFAULT_PAGE_LIMIT,
    CreatedAtSortQuery,
    LimitQuery,
    PageQuery,
    TextSearchQuery,
    apply_created_at_sort,
)
from app.api.deps import get_current_admin
from app.database import get_db
from app.models import Admin, GarmentStyle
from app.schemas.common import PaginatedResponse
from app.schemas.garment_style import GarmentStyleCreate, GarmentStyleRead, GarmentStyleStatus, GarmentStyleUpdate
from app.services.storage_service import save_upload
from app.utils.pagination import paginate

router = APIRouter(prefix="/admin/garment-styles", tags=["admin"])


def _style_or_404(db: Session, style_id: UUID) -> GarmentStyle:
    style = db.get(GarmentStyle, style_id)
    if style is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фасон не найден")
    return style


def _ensure_style_name_available(db: Session, name: str, style_id: UUID | None = None) -> None:
    stmt = select(GarmentStyle).where(func.lower(GarmentStyle.name) == name.lower())
    if style_id is not None:
        stmt = stmt.where(GarmentStyle.id != style_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Фасон с таким названием уже существует")


@router.get("", response_model=PaginatedResponse[GarmentStyleRead])
def list_styles(
    search: TextSearchQuery = None,
    status: GarmentStyleStatus | None = None,
    page: PageQuery = 1,
    limit: LimitQuery = DEFAULT_PAGE_LIMIT,
    sort: CreatedAtSortQuery = "-created_at",
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(GarmentStyle)
    stmt = apply_created_at_sort(stmt, GarmentStyle, sort)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(GarmentStyle.name.ilike(like), GarmentStyle.category.ilike(like)))
    if status:
        stmt = stmt.where(GarmentStyle.status == status)
    items, total = paginate(db, stmt, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("", response_model=GarmentStyleRead, status_code=status.HTTP_201_CREATED)
def create_style(payload: GarmentStyleCreate, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> GarmentStyle:
    _ensure_style_name_available(db, payload.name)
    style = GarmentStyle(**payload.model_dump(exclude_unset=True))
    db.add(style)
    db.commit()
    db.refresh(style)
    return style


@router.get("/{style_id}", response_model=GarmentStyleRead)
def get_style(style_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> GarmentStyle:
    return _style_or_404(db, style_id)


@router.patch("/{style_id}", response_model=GarmentStyleRead)
def update_style(style_id: UUID, payload: GarmentStyleUpdate, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> GarmentStyle:
    style = _style_or_404(db, style_id)
    if payload.name is not None:
        _ensure_style_name_available(db, payload.name, style_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(style, key, value)
    db.commit()
    db.refresh(style)
    return style


@router.post("/{style_id}/images", response_model=GarmentStyleRead, status_code=status.HTTP_201_CREATED)
async def upload_style_image(
    style_id: UUID,
    file: UploadFile = File(...),
    image_type: str = Form(...),
    _: Admin = Depends(get_current_admin),
    __: None = Depends(rate_limit_upload),
    db: Session = Depends(get_db),
) -> GarmentStyle:
    style = _style_or_404(db, style_id)
    if image_type not in {"base", "mask"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "image_type должен быть base или mask")
    image_url = await save_upload(file, "garment-styles")
    if image_type == "base":
        style.base_image_url = image_url
    else:
        style.mask_image_url = image_url
    db.commit()
    db.refresh(style)
    return style


@router.delete("/{style_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_style(style_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> None:
    db.delete(_style_or_404(db, style_id))
    db.commit()


def _set_status(db: Session, style_id: UUID, value: str) -> GarmentStyle:
    style = _style_or_404(db, style_id)
    style.status = value
    db.commit()
    db.refresh(style)
    return style


@router.post("/{style_id}/publish", response_model=GarmentStyleRead)
def publish_style(style_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> GarmentStyle:
    return _set_status(db, style_id, "published")


@router.post("/{style_id}/hide", response_model=GarmentStyleRead)
def hide_style(style_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> GarmentStyle:
    return _set_status(db, style_id, "hidden")


@router.post("/{style_id}/archive", response_model=GarmentStyleRead)
def archive_style(style_id: UUID, _: Admin = Depends(get_current_admin), db: Session = Depends(get_db)) -> GarmentStyle:
    return _set_status(db, style_id, "archived")
