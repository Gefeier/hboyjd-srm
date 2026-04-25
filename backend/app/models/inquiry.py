"""比价单/询价单模型 — 采购部核心业务

设计极简:
- Inquiry: 比价单头 (采购员创建)
- InquiryItem: 物料行 (一张单N个物料)
- InquiryInvite: 指定哪些供应商可以填这张单 (多对多)
- QuoteLine: 每个供应商针对某一 InquiryItem 的报价 (unit_price + note)

没有"Quote头"表,因为丽丽说"采购部需求就是让供应商把价填进去",不需要
报价批次/报价轮次/密封开标这些重东西。一行一行的QuoteLine就是最扁的模型。

状态只两个: open (填价中) / closed (已关闭,不能再改)。
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class InquiryStatus(StrEnum):
    OPEN = "open"          # 填价中
    CLOSED = "closed"      # 已关闭(定标/流标/取消都归这里)


class Inquiry(SQLModel, table=True):
    __tablename__ = "inquiry"
    __table_args__ = (
        Index("ix_inquiry_buyer_created", "buyer_id", "created_at"),
        Index("ix_inquiry_status_created", "status", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(sa_column=Column(String(32), unique=True, nullable=False, index=True))
    title: str = Field(sa_column=Column(String(128), nullable=False))
    remark: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # 采购员(User.id)
    buyer_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id"), nullable=False))

    # 可选的要求(非必填)
    delivery_date: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))  # "30天内"或具体日期,手填
    delivery_address: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))

    # 报价截止时间(可空 — 不设则不限期)。过此时间所有 magic link 写操作拒绝,supplier-quotes 列表显示"已截止"。
    quote_deadline: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    status: InquiryStatus = Field(
        default=InquiryStatus.OPEN,
        sa_column=Column(String(16), nullable=False, server_default="open"),
    )
    # 定标时记:采购员选了哪家
    awarded_supplier_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("supplier.id"), nullable=True),
    )
    awarded_note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    closed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )


class InquiryItem(SQLModel, table=True):
    __tablename__ = "inquiry_item"
    __table_args__ = (
        Index("ix_inquiry_item_inquiry", "inquiry_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(sa_column=Column(Integer, ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False))

    # 物料信息(手填,不走主数据)
    name: str = Field(sa_column=Column(String(128), nullable=False))
    spec: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    unit: str = Field(default="个", sa_column=Column(String(16), nullable=False))
    qty: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))
    remark: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    sort_order: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))


class InquiryInvite(SQLModel, table=True):
    """比价单邀标记录:标识哪些供应商可以填这张单。
    token 用于生成 magic link — 供应商不用注册登录,点链接直接填价。
    """
    __tablename__ = "inquiry_invite"
    __table_args__ = (
        Index("ix_invite_inquiry_supplier", "inquiry_id", "supplier_id", unique=True),
        Index("ix_invite_supplier_inquiry", "supplier_id", "inquiry_id"),
        Index("ix_invite_token", "token", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(sa_column=Column(Integer, ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False))
    supplier_id: int = Field(sa_column=Column(Integer, ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False))
    # magic link token — 43 字符 URL-safe base64(32字节随机)
    token: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    invited_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    # 首次提交报价的时间(若null说明还没填)
    quoted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class QuoteLine(SQLModel, table=True):
    """每一行: 某供应商对某一 InquiryItem 的单价报价"""
    __tablename__ = "quote_line"
    __table_args__ = (
        Index("ix_qline_item_supplier", "inquiry_item_id", "supplier_id", unique=True),
        Index("ix_qline_supplier_inquiry", "supplier_id", "inquiry_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(sa_column=Column(Integer, ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False))
    inquiry_item_id: int = Field(sa_column=Column(Integer, ForeignKey("inquiry_item.id", ondelete="CASCADE"), nullable=False))
    supplier_id: int = Field(sa_column=Column(Integer, ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False))

    unit_price: Decimal = Field(sa_column=Column(Numeric(14, 4), nullable=False))
    note: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )
