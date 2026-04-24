"""新增 quote_row 和 quote_attachment 两张表 (供应商主动报价模式)"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0006"
down_revision = "20260424_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========== quote_row ==========
    op.create_table(
        "quote_row",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=256), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_qrow_inquiry_supplier", "quote_row", ["inquiry_id", "supplier_id"])
    op.create_index("ix_qrow_supplier_inquiry", "quote_row", ["supplier_id", "inquiry_id"])

    # ========== quote_attachment ==========
    op.create_table(
        "quote_attachment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("parse_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("parse_note", sa.String(length=512), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_qatt_inquiry_supplier", "quote_attachment", ["inquiry_id", "supplier_id"])


def downgrade() -> None:
    op.drop_table("quote_attachment")
    op.drop_table("quote_row")
