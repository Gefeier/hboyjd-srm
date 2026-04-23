from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Column, DateTime, Index, JSON, Numeric, String, Text, desc
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


# 用 StrEnum (Python 3.11+):str(instance) 直接返回 value,SQLAlchemy 存 VARCHAR 可直接塞
class TaxpayerType(StrEnum):
    GENERAL = "general"
    SMALL_SCALE = "small_scale"


class SupplierStatus(StrEnum):
    PENDING_PROFILE = "pending_profile"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FROZEN = "frozen"


class SupplierSource(StrEnum):
    SELF_REGISTER = "self_register"
    KINGDEE_IMPORT = "kingdee_import"
    MANUAL = "manual"


class SupplierGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"
    __table_args__ = (
        Index("ix_supplier_status_created_at", "status", desc("created_at")),
        Index("ix_supplier_unified_credit_code", "unified_credit_code"),
        Index("ix_supplier_company_name", "company_name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(sa_column=Column(String(32), unique=True, nullable=False, index=True))

    # === 最小注册信息(必填)===
    company_name: str = Field(sa_column=Column(String(128), unique=True, nullable=False))
    contact_phone: str = Field(sa_column=Column(String(20), nullable=False))  # 兼作注册入口+工作台联系电话
    login_username: str = Field(sa_column=Column(String(32), unique=True, nullable=False))
    login_password_hash: str = Field(sa_column=Column(String(256), nullable=False))

    # === 资料补全时填(可选,允许空)===
    unified_credit_code: str | None = Field(default=None, sa_column=Column(String(18), unique=True, nullable=True))
    legal_person: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    founded_date: date | None = Field(default=None)
    registered_address: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    registered_capital: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    company_type: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    taxpayer_type: TaxpayerType | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    business_intro: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # 联系人补充字段
    contact_name: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    contact_email: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    contact_position: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    wechat: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    landline: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))

    # === 状态/分级 ===
    status: SupplierStatus = Field(default=SupplierStatus.PENDING_PROFILE, sa_column=Column(String(32), nullable=False, server_default="pending_profile"))
    source: SupplierSource = Field(default=SupplierSource.SELF_REGISTER, sa_column=Column(String(32), nullable=False, server_default="self_register"))
    grade: SupplierGrade | None = Field(default=None, sa_column=Column(String(4), nullable=True))
    review_note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    reviewed_by: int | None = Field(default=None, foreign_key="user.id")
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    categories: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    qualifications: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )

    @property
    def profile_completed(self) -> bool:
        """资料补全判断:关键字段都不为空才算完成"""
        required = [
            self.unified_credit_code,
            self.legal_person,
            self.registered_address,
            self.contact_name,
            self.contact_email,
        ]
        return all(f for f in required) and bool(self.categories)
