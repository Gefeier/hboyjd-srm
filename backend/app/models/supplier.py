from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Index, JSON, Numeric, String, Text, desc
from sqlmodel import Field, SQLModel


def _pg_enum(enum_cls, name):
    """创建列枚举,按 .value 持久化(而不是默认的 .name)"""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
    )


def utcnow() -> datetime:
    return datetime.now(UTC)


class TaxpayerType(str, Enum):
    GENERAL = "general"
    SMALL_SCALE = "small_scale"


class SupplierStatus(str, Enum):
    PENDING_PROFILE = "pending_profile"  # 刚注册,尚未完善资料
    PENDING = "pending"                  # 已提交资料,等审核
    APPROVED = "approved"                # 审核通过,合格供应商
    REJECTED = "rejected"                # 审核驳回
    FROZEN = "frozen"                    # 冻结/暂停


class SupplierSource(str, Enum):
    SELF_REGISTER = "self_register"  # 供应商自己网站注册
    KINGDEE_IMPORT = "kingdee_import"  # 从金蝶ERP批量导入的老供应商
    MANUAL = "manual"                 # 采购员手工建档


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
    taxpayer_type: TaxpayerType | None = Field(default=None, sa_column=Column(_pg_enum(TaxpayerType, "taxpayertype"), nullable=True))
    business_intro: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # 联系人补充字段
    contact_name: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    contact_email: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    contact_position: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    wechat: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    landline: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))

    # === 状态/分级 ===
    status: SupplierStatus = Field(default=SupplierStatus.PENDING_PROFILE, sa_column=Column(_pg_enum(SupplierStatus, "supplierstatus"), nullable=False))
    source: SupplierSource = Field(default=SupplierSource.SELF_REGISTER, sa_column=Column(_pg_enum(SupplierSource, "suppliersource"), nullable=False, server_default="self_register"))
    grade: SupplierGrade | None = Field(default=None, sa_column=Column(_pg_enum(SupplierGrade, "suppliergrade"), nullable=True))
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
