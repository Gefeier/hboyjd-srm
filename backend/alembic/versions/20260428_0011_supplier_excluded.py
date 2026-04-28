"""supplier 加 excluded_from_rfq + excluded_reason — 不参与询价开关"""

from alembic import op
import sqlalchemy as sa


revision = "20260428_0011"
down_revision = "20260425_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier",
        sa.Column("excluded_from_rfq", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "supplier",
        sa.Column("excluded_reason", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("supplier", "excluded_reason")
    op.drop_column("supplier", "excluded_from_rfq")
