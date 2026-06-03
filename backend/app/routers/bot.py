from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Fabric, TelegramUser
from ..schemas import SelectedFabricResponse, SelectFabricRequest, TelegramUserOut, TelegramUserUpsert

router = APIRouter(prefix="/api/bot", tags=["telegram-bot"])

# Public Telegram-bot endpoints. Keep this module isolated so a future BOT_INTERNAL_TOKEN
# dependency can be added to this router without touching handlers or catalog routes.


@router.post("/users/upsert", response_model=TelegramUserOut)
def upsert_telegram_user(payload: TelegramUserUpsert, db: Session = Depends(get_db)) -> TelegramUser:
    user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == payload.telegram_id))
    if user is None:
        user = TelegramUser(telegram_id=payload.telegram_id)
        db.add(user)

    user.username = payload.username
    user.first_name = payload.first_name
    user.last_name = payload.last_name
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{telegram_id}/selected-fabric", response_model=SelectedFabricResponse)
def select_fabric_for_user(
    telegram_id: int, payload: SelectFabricRequest, db: Session = Depends(get_db)
) -> SelectedFabricResponse:
    user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        user = TelegramUser(telegram_id=telegram_id)
        db.add(user)
        db.flush()

    fabric = db.scalar(
        select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == payload.fabric_id)
    )
    if fabric is None:
        raise HTTPException(status_code=404, detail="Fabric not found")
    if fabric.status != "published":
        raise HTTPException(status_code=403, detail="Only published fabrics can be selected")

    user.selected_fabric_id = fabric.id
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fabric)
    return SelectedFabricResponse(selected=True, message="Ткань выбрана.", fabric=fabric)


@router.get("/users/{telegram_id}/selected-fabric", response_model=SelectedFabricResponse)
def get_selected_fabric(telegram_id: int, db: Session = Depends(get_db)) -> SelectedFabricResponse:
    user = db.scalar(
        select(TelegramUser)
        .options(selectinload(TelegramUser.selected_fabric).selectinload(Fabric.images))
        .where(TelegramUser.telegram_id == telegram_id)
    )
    if user is None or user.selected_fabric is None:
        return SelectedFabricResponse(selected=False, message="Вы пока не выбрали ткань.", fabric=None)
    return SelectedFabricResponse(selected=True, message="Выбранная ткань.", fabric=user.selected_fabric)
