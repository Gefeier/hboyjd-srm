"""material 物料主档 — 用过即归档,可复用"""

from alembic import op
import sqlalchemy as sa


revision = "20260428_0013"
down_revision = "20260428_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=256), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="个"),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_buyer_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_material_category_last_used", "material", ["category", "last_used_at"])
    op.create_index("ix_material_name", "material", ["name"])


def downgrade() -> None:
    op.drop_index("ix_material_name", table_name="material")
    op.drop_index("ix_material_category_last_used", table_name="material")
    op.drop_table("material")
