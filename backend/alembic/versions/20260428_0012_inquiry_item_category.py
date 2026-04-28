"""inquiry_item 加 category — 物料大类(用于自动推荐供应商)"""

from alembic import op
import sqlalchemy as sa


revision = "20260428_0012"
down_revision = "20260428_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inquiry_item",
        sa.Column("category", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inquiry_item", "category")
