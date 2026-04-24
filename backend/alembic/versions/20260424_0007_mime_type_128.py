"""扩大 quote_attachment.mime_type 字段 64 → 128 字符

office OOXML 的 MIME 有些 65+ 字符(xlsx=65, docx=71),64 不够装,写入会 500
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0007"
down_revision = "20260424_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "quote_attachment",
        "mime_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "quote_attachment",
        "mime_type",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
