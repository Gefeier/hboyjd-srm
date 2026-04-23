"""supplier_onboarding: 简易注册 - 字段nullable+加pending_profile/source"""

from alembic import op
import sqlalchemy as sa


revision = "20260423_0002"
down_revision = "20260421_0001"
branch_labels = None
depends_on = None


supplier_source = sa.Enum("self_register", "kingdee_import", "manual", name="suppliersource")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. 枚举新增 pending_profile 值 (PG 需要在 autocommit 块)
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE supplierstatus ADD VALUE IF NOT EXISTS 'pending_profile'")
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'supplier'")

    # 2. 创建 suppliersource 枚举
    supplier_source.create(bind, checkfirst=True)

    # 3. 加 source 列
    op.add_column(
        "supplier",
        sa.Column(
            "source",
            supplier_source,
            nullable=False,
            server_default="self_register",
        ),
    )

    # 4. 字段改 nullable (金蝶导入/简易注册时没这些数据)
    op.alter_column("supplier", "unified_credit_code", nullable=True)
    op.alter_column("supplier", "legal_person", nullable=True)
    op.alter_column("supplier", "contact_name", nullable=True)
    op.alter_column("supplier", "contact_email", nullable=True)


def downgrade() -> None:
    op.alter_column("supplier", "contact_email", nullable=False)
    op.alter_column("supplier", "contact_name", nullable=False)
    op.alter_column("supplier", "legal_person", nullable=False)
    op.alter_column("supplier", "unified_credit_code", nullable=False)
    op.drop_column("supplier", "source")
    supplier_source.drop(op.get_bind(), checkfirst=True)
    # enum 值新增无法简单回滚 (pending_profile/supplier),跳过
