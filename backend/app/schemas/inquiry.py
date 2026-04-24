from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.inquiry import InquiryStatus


# ============== 采购员端:创建/查询比价单 ==============

class InquiryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=256)
    unit: str = Field(default="个", max_length=16)
    qty: Decimal = Field(gt=0)
    remark: str | None = Field(default=None, max_length=256)


class InquiryCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128)
    remark: str | None = Field(default=None, max_length=2000)
    delivery_date: str | None = Field(default=None, max_length=32)
    delivery_address: str | None = Field(default=None, max_length=256)
    items: list[InquiryItemCreate] = Field(min_length=1)  # 至少一行物料
    supplier_ids: list[int] = Field(min_length=1)  # 至少邀请1家

    @field_validator("items")
    @classmethod
    def non_empty_items(cls, v):
        if not v:
            raise ValueError("至少添加一行物料")
        return v


class InquiryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    spec: str | None = None
    unit: str
    qty: Decimal
    remark: str | None = None
    sort_order: int = 0


class SupplierMini(BaseModel):
    """比价单上显示的供应商迷你信息"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    company_name: str
    contact_phone: str | None = None


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    supplier_id: int
    invited_at: datetime
    quoted_at: datetime | None = None


class QuoteLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inquiry_item_id: int
    supplier_id: int
    unit_price: Decimal
    note: str | None = None
    updated_at: datetime


class InquiryRead(BaseModel):
    """列表用:不含items/quotes,轻量"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str
    remark: str | None = None
    buyer_id: int
    buyer_name: str | None = None
    status: InquiryStatus
    delivery_date: str | None = None
    delivery_address: str | None = None
    awarded_supplier_id: int | None = None
    awarded_supplier_name: str | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # 汇总
    item_count: int = 0
    invited_count: int = 0
    quoted_count: int = 0  # 已有报价的供应商数(只要提交过一行就算)


class InquiryDetail(InquiryRead):
    """详情:含全部 items / suppliers / quote_lines"""
    items: list[InquiryItemRead] = []
    suppliers: list[SupplierMini] = []
    invites: list[InviteRead] = []
    quote_lines: list[QuoteLineRead] = []


class InquiryListResponse(BaseModel):
    items: list[InquiryRead]
    total: int
    page: int
    page_size: int


class InquiryAwardRequest(BaseModel):
    supplier_id: int
    note: str | None = None


# ============== 供应商端:填报价 ==============

class MyInquiryItem(BaseModel):
    """供应商端看到的一行:物料信息 + 自己填的价格(若有)"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    spec: str | None = None
    unit: str
    qty: Decimal
    remark: str | None = None
    sort_order: int = 0
    my_unit_price: Decimal | None = None  # 自己之前填的(若有)
    my_note: str | None = None


class MyInquiryDetail(BaseModel):
    """供应商端打开单张比价单的视图"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str
    remark: str | None = None
    delivery_date: str | None = None
    delivery_address: str | None = None
    status: InquiryStatus
    created_at: datetime
    quoted_at: datetime | None = None  # 我首次提交时间
    items: list[MyInquiryItem] = []


class MyQuoteLineSubmit(BaseModel):
    item_id: int
    unit_price: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=256)


class MyQuoteSubmit(BaseModel):
    lines: list[MyQuoteLineSubmit] = Field(min_length=1)
