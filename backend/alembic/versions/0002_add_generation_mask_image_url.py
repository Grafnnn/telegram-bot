"""add generation mask image url"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_generation_mask_image_url"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("mask_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "mask_image_url")
