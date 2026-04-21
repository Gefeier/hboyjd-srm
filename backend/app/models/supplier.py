from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, DateTime, Index, JSON, Numeric, String, Text, desc
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class TaxpayerType(str, Enum):
    GENERAL = "general"
    SMALL_SCALE = "small_scale"


class SupplierStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FROZEN = "frozen"


class SupplierGrade(str, Enum):
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
    company_name: str = Field(sa_column=Column(String(128), unique=True, nullable=False))
    unified_credit_code: str = Field(sa_column=Column(String(18), unique=True, nullable=False))
    legal_person: str = Field(sa_column=Column(String(32), nullable=False))
    founded_date: date | None = Field(default=None)
    registered_address: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    registered_capital: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    company_type: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    taxpayer_type: TaxpayerType | None = Field(default=None, nullable=True)
    business_intro: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    contact_name: str = Field(sa_column=Column(String(32), nullable=False))
    contact_phone: str = Field(sa_column=Column(String(20), nullable=False))
    contact_email: str = Field(sa_column=Column(String(128), nullable=False))
    contact_position: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    wechat: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    landline: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    login_username: str = Field(sa_column=Column(String(32), unique=True, nullable=False))
    login_password_hash: str = Field(sa_column=Column(String(256), nullable=False))
    status: SupplierStatus = Field(default=SupplierStatus.PENDING, nullable=False)
    grade: SupplierGrade | None = Field(default=None, nullable=True)
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
