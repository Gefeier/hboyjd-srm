"""供应商主动报价模型 (方式4混合型 · 供应商自己列清单)

和原先 InquiryItem+QuoteLine 的区别:
- 那套是"采购员列物料,供应商填价" — 保留兼容旧单
- 这套是"供应商自己列他能供的清单+价" — 新模型,核心

两张表:
- QuoteRow:供应商填的每一行(名称/规格/单位/数量/单价/备注/来源)
- QuoteAttachment:供应商上传的附件(PDF/Excel/图片),可选 AI 解析
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class QuoteRowSource(StrEnum):
    MANUAL = "manual"          # 供应商手填
    AI_PARSED = "ai_parsed"    # AI 从附件解析
    ADMIN = "admin"            # 采购员代填


class QuoteRow(SQLModel, table=True):
    """供应商的报价行(自由清单,每家填啥是啥)"""
    __tablename__ = "quote_row"
    __table_args__ = (
        Index("ix_qrow_inquiry_supplier", "inquiry_id", "supplier_id"),
        Index("ix_qrow_supplier_inquiry", "supplier_id", "inquiry_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(sa_column=Column(Integer, ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False))
    supplier_id: int = Field(sa_column=Column(Integer, ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False))

    name: str = Field(sa_column=Column(String(128), nullable=False))
    spec: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    unit: str = Field(default="个", sa_column=Column(String(16), nullable=False))
    qty: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    unit_price: Decimal = Field(sa_column=Column(Numeric(14, 4), nullable=False))
    note: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    source: QuoteRowSource = Field(
        default=QuoteRowSource.MANUAL,
        sa_column=Column(String(16), nullable=False, server_default="manual"),
    )
    sort_order: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )


class QuoteAttachment(SQLModel, table=True):
    """供应商上传的报价附件 (PDF/Excel/图片)"""
    __tablename__ = "quote_attachment"
    __table_args__ = (
        Index("ix_qatt_inquiry_supplier", "inquiry_id", "supplier_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(sa_column=Column(Integer, ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False))
    supplier_id: int = Field(sa_column=Column(Integer, ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False))

    filename: str = Field(sa_column=Column(String(256), nullable=False))  # 原始文件名
    storage_path: str = Field(sa_column=Column(String(512), nullable=False))  # 服务器相对路径
    file_size: int = Field(sa_column=Column(Integer, nullable=False))
    mime_type: str = Field(sa_column=Column(String(128), nullable=False))

    # AI 解析状态
    parse_status: str = Field(
        default="pending",
        sa_column=Column(String(16), nullable=False, server_default="pending"),
    )  # pending / parsing / done / failed / skipped
    parse_note: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    parsed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    uploaded_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
