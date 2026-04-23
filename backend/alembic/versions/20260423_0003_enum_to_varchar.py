"""enum_to_varchar: 改用 VARCHAR + StrEnum 避免大小写枚举地狱"""

from alembic import op
import sqlalchemy as sa


revision = "20260423_0003"
down_revision = "20260423_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 把 enum 列全部转成 VARCHAR
    op.execute('ALTER TABLE "user" ALTER COLUMN role TYPE varchar(16) USING role::text')
    op.execute('ALTER TABLE supplier ALTER COLUMN status TYPE varchar(32) USING status::text')
    op.execute('ALTER TABLE supplier ALTER COLUMN source TYPE varchar(32) USING source::text')
    op.execute('ALTER TABLE supplier ALTER COLUMN grade TYPE varchar(4) USING grade::text')
    op.execute('ALTER TABLE supplier ALTER COLUMN taxpayer_type TYPE varchar(32) USING taxpayer_type::text')

    # 2. 把旧的 UPPERCASE 历史数据小写化 (SupplierGrade A/B/C/D 保持大写)
    op.execute("UPDATE \"user\" SET role = lower(role)")
    op.execute("UPDATE supplier SET status = lower(status)")
    op.execute("UPDATE supplier SET source = lower(source) WHERE source IS NOT NULL")
    op.execute("UPDATE supplier SET taxpayer_type = lower(taxpayer_type) WHERE taxpayer_type IS NOT NULL")

    # 3. 清理 PG enum 类型 (已无列引用)
    op.execute("DROP TYPE IF EXISTS supplierstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
    op.execute("DROP TYPE IF EXISTS suppliergrade CASCADE")
    op.execute("DROP TYPE IF EXISTS taxpayertype CASCADE")
    op.execute("DROP TYPE IF EXISTS suppliersource CASCADE")


def downgrade() -> None:
    # 不走回头路,跳过(enum DROP 后无法简单还原)
    pass
