"""inquiry 加 quote_deadline 字段 — 报价截止日"""

from alembic import op
import sqlalchemy as sa


revision = "20260425_0010"
down_revision = "20260424_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inquiry",
        sa.Column("quote_deadline", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inquiry", "quote_deadline")
