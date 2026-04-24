"""比价单相关4张表: inquiry / inquiry_item / inquiry_invite / quote_line"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0004"
down_revision = "20260423_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========== inquiry 头表 ==========
    op.create_table(
        "inquiry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("delivery_date", sa.String(length=32), nullable=True),
        sa.Column("delivery_address", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("awarded_supplier_id", sa.Integer(), sa.ForeignKey("supplier.id"), nullable=True),
        sa.Column("awarded_note", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inquiry_code", "inquiry", ["code"], unique=True)
    op.create_index("ix_inquiry_buyer_created", "inquiry", ["buyer_id", "created_at"])
    op.create_index("ix_inquiry_status_created", "inquiry", ["status", "created_at"])

    # ========== inquiry_item ==========
    op.create_table(
        "inquiry_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=256), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Numeric(14, 2), nullable=False),
        sa.Column("remark", sa.String(length=256), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_inquiry_item_inquiry", "inquiry_item", ["inquiry_id"])

    # ========== inquiry_invite ==========
    op.create_table(
        "inquiry_invite",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_invite_inquiry_supplier", "inquiry_invite", ["inquiry_id", "supplier_id"], unique=True)
    op.create_index("ix_invite_supplier_inquiry", "inquiry_invite", ["supplier_id", "inquiry_id"])

    # ========== quote_line ==========
    op.create_table(
        "quote_line",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inquiry_item_id", sa.Integer(), sa.ForeignKey("inquiry_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_qline_item_supplier", "quote_line", ["inquiry_item_id", "supplier_id"], unique=True)
    op.create_index("ix_qline_supplier_inquiry", "quote_line", ["supplier_id", "inquiry_id"])


def downgrade() -> None:
    op.drop_table("quote_line")
    op.drop_table("inquiry_invite")
    op.drop_table("inquiry_item")
    op.drop_table("inquiry")
