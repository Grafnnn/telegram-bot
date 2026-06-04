"""Fabric model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Fabric(Base):
    __tablename__ = "fabrics"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    sku: Mapped[str] = mapped_column(Text, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    composition: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)
    shade: Mapped[str | None] = mapped_column(Text)
    pattern: Mapped[str | None] = mapped_column(Text)
    texture: Mapped[str | None] = mapped_column(Text)
    density: Mapped[str | None] = mapped_column(Text)
    stretch: Mapped[str | None] = mapped_column(Text)
    opacity: Mapped[str | None] = mapped_column(Text)
    shine: Mapped[str | None] = mapped_column(Text)
    season: Mapped[list[str] | None] = mapped_column(JSONB)
    recommended_for: Mapped[list[str] | None] = mapped_column(JSONB)
    not_recommended_for: Mapped[list[str] | None] = mapped_column(JSONB)
    price_per_meter: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, nullable=False, default="RUB", server_default="RUB")
    stock_status: Mapped[str] = mapped_column(String, nullable=False, default="in_stock", server_default="in_stock")
    stock_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    short_description: Mapped[str | None] = mapped_column(Text)
    full_description: Mapped[str | None] = mapped_column(Text)
    description_for_gpt: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft", server_default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    images = relationship("FabricImage", back_populates="fabric", cascade="all, delete-orphan")
    generations = relationship("Generation", back_populates="fabric")
