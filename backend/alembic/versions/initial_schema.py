"""initial schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admins_email", "admins", ["email"], unique=True)

    op.create_table(
        "fabrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("composition", sa.Text()),
        sa.Column("color", sa.Text()),
        sa.Column("shade", sa.Text()),
        sa.Column("pattern", sa.Text()),
        sa.Column("texture", sa.Text()),
        sa.Column("density", sa.Text()),
        sa.Column("stretch", sa.Text()),
        sa.Column("opacity", sa.Text()),
        sa.Column("shine", sa.Text()),
        sa.Column("season", postgresql.JSONB()),
        sa.Column("recommended_for", postgresql.JSONB()),
        sa.Column("not_recommended_for", postgresql.JSONB()),
        sa.Column("price_per_meter", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(), nullable=False, server_default="RUB"),
        sa.Column("stock_status", sa.String(), nullable=False, server_default="in_stock"),
        sa.Column("stock_quantity", sa.Numeric(12, 2)),
        sa.Column("short_description", sa.Text()),
        sa.Column("full_description", sa.Text()),
        sa.Column("description_for_gpt", sa.Text()),
        sa.Column("tags", postgresql.JSONB()),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fabrics_sku", "fabrics", ["sku"], unique=True)
    op.create_index("ix_fabrics_status", "fabrics", ["status"])

    op.create_table(
        "garment_styles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("compatible_fabric_categories", postgresql.JSONB()),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("base_image_url", sa.Text()),
        sa.Column("mask_image_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_garment_styles_status", "garment_styles", ["status"])

    op.create_table(
        "telegram_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String()),
        sa.Column("first_name", sa.String()),
        sa.Column("last_name", sa.String()),
        sa.Column("selected_fabric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fabrics.id", ondelete="SET NULL")),
        sa.Column("selected_garment_style_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("garment_styles.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_telegram_users_telegram_id", "telegram_users", ["telegram_id"], unique=True)

    op.create_table(
        "fabric_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fabric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fabrics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_type", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fabric_images_fabric_id", "fabric_images", ["fabric_id"])

    op.create_table(
        "generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("telegram_users.id", ondelete="SET NULL")),
        sa.Column("fabric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fabrics.id", ondelete="SET NULL")),
        sa.Column("garment_style_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("garment_styles.id", ondelete="SET NULL")),
        sa.Column("user_photo_url", sa.Text()),
        sa.Column("result_image_url", sa.Text()),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text()),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_generations_telegram_user_id", "generations", ["telegram_user_id"])
    op.create_index("ix_generations_fabric_id", "generations", ["fabric_id"])
    op.create_index("ix_generations_garment_style_id", "generations", ["garment_style_id"])
    op.create_index("ix_generations_status", "generations", ["status"])


def downgrade() -> None:
    op.drop_table("generations")
    op.drop_table("fabric_images")
    op.drop_table("telegram_users")
    op.drop_table("garment_styles")
    op.drop_table("fabrics")
    op.drop_table("admins")
