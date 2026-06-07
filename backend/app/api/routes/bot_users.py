"""Bot-facing Telegram user routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.rate_limit import rate_limit_bot_api
from app.api.deps import verify_bot_internal_token
from app.database import get_db
from app.models import Fabric, GarmentStyle, TelegramUser
from app.schemas.telegram_user import (
    SelectedFabricRead,
    SelectedFabricUpdate,
    SelectedGarmentStyleRead,
    SelectedGarmentStyleUpdate,
    TelegramSelectionRead,
    TelegramUserRead,
    TelegramUserUpsert,
)

router = APIRouter(
    prefix="/bot",
    tags=["bot"],
    dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_bot_api)],
)


def _telegram_user_or_404(db: Session, telegram_id: int) -> TelegramUser:
    user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь Telegram не найден")
    return user


def _fabric_with_images_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id))
    if fabric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    return fabric


def _style_or_404(db: Session, style_id: UUID) -> GarmentStyle:
    style = db.get(GarmentStyle, style_id)
    if style is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фасон не найден")
    return style


def _selected_fabric(db: Session, user: TelegramUser) -> Fabric | None:
    if user.selected_fabric_id is None:
        return None
    fabric = _fabric_with_images_or_404(db, user.selected_fabric_id)
    return fabric if fabric.status == "published" else None


def _selected_style(db: Session, user: TelegramUser) -> GarmentStyle | None:
    if user.selected_garment_style_id is None:
        return None
    style = _style_or_404(db, user.selected_garment_style_id)
    return style if style.status == "published" else None


@router.post("/users/upsert", response_model=TelegramUserRead)
def upsert_telegram_user(payload: TelegramUserUpsert, db: Session = Depends(get_db)) -> TelegramUser:
    user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == payload.telegram_id))
    if user is None:
        user = TelegramUser(telegram_id=payload.telegram_id)
        db.add(user)
    user.username = payload.username
    user.first_name = payload.first_name
    user.last_name = payload.last_name
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{telegram_id}/selected-fabric", response_model=TelegramUserRead)
def select_fabric_for_user(telegram_id: int, payload: SelectedFabricUpdate, db: Session = Depends(get_db)) -> TelegramUser:
    user = _telegram_user_or_404(db, telegram_id)
    fabric = _fabric_with_images_or_404(db, payload.fabric_id)
    if fabric.status != "published":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Можно выбрать только опубликованную ткань")
    user.selected_fabric_id = fabric.id
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{telegram_id}/selected-fabric", response_model=SelectedFabricRead)
def get_selected_fabric_for_user(telegram_id: int, db: Session = Depends(get_db)) -> dict:
    user = _telegram_user_or_404(db, telegram_id)
    fabric = _selected_fabric(db, user)
    if fabric is None:
        return {"fabric": None, "message": "Вы пока не выбрали ткань."}
    return {"fabric": fabric, "message": "Выбранная ткань."}


@router.post("/users/{telegram_id}/selected-garment-style", response_model=TelegramUserRead)
def select_garment_style_for_user(telegram_id: int, payload: SelectedGarmentStyleUpdate, db: Session = Depends(get_db)) -> TelegramUser:
    user = _telegram_user_or_404(db, telegram_id)
    style = _style_or_404(db, payload.garment_style_id)
    if style.status != "published":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Можно выбрать только опубликованный фасон")
    user.selected_garment_style_id = style.id
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{telegram_id}/selected-garment-style", response_model=SelectedGarmentStyleRead)
def get_selected_garment_style_for_user(telegram_id: int, db: Session = Depends(get_db)) -> dict:
    user = _telegram_user_or_404(db, telegram_id)
    style = _selected_style(db, user)
    if style is None:
        return {"garment_style": None, "message": "Вы пока не выбрали фасон."}
    return {"garment_style": style, "message": "Выбранный фасон."}


@router.get("/users/{telegram_id}/selection", response_model=TelegramSelectionRead)
def get_user_selection(telegram_id: int, db: Session = Depends(get_db)) -> dict:
    user = _telegram_user_or_404(db, telegram_id)
    return {
        "fabric": _selected_fabric(db, user),
        "garment_style": _selected_style(db, user),
        "message": "Текущий выбор пользователя.",
    }
