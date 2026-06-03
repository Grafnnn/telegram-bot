"""Garment style model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GarmentStyle(Base):
    __tablename__ = "garment_styles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    compatible_fabric_categories: Mapped[list[str] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft", server_default="draft", index=True)
    base_image_url: Mapped[str | None] = mapped_column(Text)
    mask_image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    generations = relationship("Generation", back_populates="garment_style")
