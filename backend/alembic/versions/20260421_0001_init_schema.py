"""init schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role = sa.Enum("admin", "buyer", "approver", name="userrole")
taxpayer_type = sa.Enum("general", "small_scale", name="taxpayertype")
supplier_status = sa.Enum("pending", "approved", "rejected", "frozen", name="supplierstatus")
supplier_grade = sa.Enum("A", "B", "C", "D", name="suppliergrade")


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    taxpayer_type.create(bind, checkfirst=True)
    supplier_status.create(bind, checkfirst=True)
    supplier_grade.create(bind, checkfirst=True)

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_user_username"),
    )
    op.create_index("ix_user_username", "user", ["username"], unique=False)

    op.create_table(
        "supplier",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=128), nullable=False),
        sa.Column("unified_credit_code", sa.String(length=18), nullable=False),
        sa.Column("legal_person", sa.String(length=32), nullable=False),
        sa.Column("founded_date", sa.Date(), nullable=True),
        sa.Column("registered_address", sa.String(length=256), nullable=True),
        sa.Column("registered_capital", sa.Numeric(12, 2), nullable=True),
        sa.Column("company_type", sa.String(length=32), nullable=True),
        sa.Column("taxpayer_type", taxpayer_type, nullable=True),
        sa.Column("business_intro", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(length=32), nullable=False),
        sa.Column("contact_phone", sa.String(length=20), nullable=False),
        sa.Column("contact_email", sa.String(length=128), nullable=False),
        sa.Column("contact_position", sa.String(length=32), nullable=True),
        sa.Column("wechat", sa.String(length=64), nullable=True),
        sa.Column("landline", sa.String(length=32), nullable=True),
        sa.Column("login_username", sa.String(length=32), nullable=False),
        sa.Column("login_password_hash", sa.String(length=256), nullable=False),
        sa.Column("status", supplier_status, nullable=False, server_default="pending"),
        sa.Column("grade", supplier_grade, nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("qualifications", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_supplier_code"),
        sa.UniqueConstraint("company_name", name="uq_supplier_company_name"),
        sa.UniqueConstraint("unified_credit_code", name="uq_supplier_credit_code"),
        sa.UniqueConstraint("login_username", name="uq_supplier_login_username"),
    )
    op.create_index("ix_supplier_code", "supplier", ["code"], unique=False)
    op.create_index("ix_supplier_status_created_at", "supplier", ["status", "created_at"], unique=False)
    op.create_index("ix_supplier_unified_credit_code", "supplier", ["unified_credit_code"], unique=False)
    op.create_index("ix_supplier_company_name", "supplier", ["company_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_supplier_company_name", table_name="supplier")
    op.drop_index("ix_supplier_unified_credit_code", table_name="supplier")
    op.drop_index("ix_supplier_status_created_at", table_name="supplier")
    op.drop_index("ix_supplier_code", table_name="supplier")
    op.drop_table("supplier")
    op.drop_index("ix_user_username", table_name="user")
    op.drop_table("user")

    bind = op.get_bind()
    supplier_grade.drop(bind, checkfirst=True)
    supplier_status.drop(bind, checkfirst=True)
    taxpayer_type.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
