"""Startup seed helpers."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fabric, GarmentStyle
from app.services.auth_service import ensure_initial_admin

DEMO_FABRIC_SKU = "DEMO-SILK-001"
DEMO_STYLE_NAME = "Платье А-силуэта"


def seed_initial_admin(db: Session, email: str, password: str) -> None:
    ensure_initial_admin(db, email, password)


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Fabric).where(Fabric.sku == DEMO_FABRIC_SKU)) is None:
        db.add(
            Fabric(
                sku=DEMO_FABRIC_SKU,
                name="Демо шелк",
                category="шелк",
                color="молочный",
                price_per_meter=2500,
                status="draft",
                description_for_gpt="Легкий демо шелк для платьев.",
            )
        )
    if db.scalar(select(GarmentStyle).where(GarmentStyle.name == DEMO_STYLE_NAME)) is None:
        db.add(
            GarmentStyle(
                name=DEMO_STYLE_NAME,
                category="платья",
                description="Базовый демо фасон",
                status="draft",
            )
        )
    db.commit()
