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
    remark: str | None = Field(default=None, max_length=4000)  # 详细需求说明 — 多行
    delivery_date: str | None = Field(default=None, max_length=32)
    delivery_address: str | None = Field(default=None, max_length=256)
    quote_deadline: datetime | None = None  # 报价截止时间(可空)
    # items 可选 — 方式4混合型:采购员可不列,让供应商自己报
    items: list[InquiryItemCreate] = Field(default_factory=list)
    supplier_ids: list[int] = Field(min_length=1)


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
    token: str  # 供采购员复制 magic link 用
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
    quote_deadline: datetime | None = None
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


class InquiryUpdate(BaseModel):
    """编辑询价单 — 只改基本信息(物料和邀请名单不在此处改)"""
    title: str | None = Field(default=None, min_length=2, max_length=128)
    remark: str | None = Field(default=None, max_length=4000)
    delivery_date: str | None = Field(default=None, max_length=32)
    delivery_address: str | None = Field(default=None, max_length=256)
    quote_deadline: datetime | None = None  # null 表示清除截止;不传(unset)则不改


# ============== 采购员端:看每家的报价详情(方式4) ==============

class AdminQuoteRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    spec: str | None = None
    unit: str
    qty: Decimal | None = None
    unit_price: Decimal
    note: str | None = None
    source: str
    sort_order: int = 0


class AdminAttachment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    file_size: int
    mime_type: str
    parse_status: str
    parse_note: str | None = None
    uploaded_at: datetime


class SupplierQuoteDetail(BaseModel):
    """采购员视角:一家供应商针对此询价单的完整报价(含附件+自填行+预设报价)"""
    supplier_id: int
    supplier_code: str
    company_name: str
    contact_phone: str | None = None
    quoted_at: datetime | None = None
    rows: list[AdminQuoteRow] = []
    attachments: list[AdminAttachment] = []
    total_amount: Decimal = Decimal("0")  # 有qty的行:qty×price;无qty的行:只累加unit_price一次
    row_count: int = 0
    revision_count: int = 0    # 已提交版本数
    current_version: int | None = None  # 当前展示的版本号


class InquirySupplierQuotesResponse(BaseModel):
    inquiry_id: int
    inquiry_code: str
    suppliers: list[SupplierQuoteDetail] = []


# ============== 调价历史(版本) ==============

class RevisionRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    spec: str | None = None
    unit: str
    qty: Decimal | None = None
    unit_price: Decimal
    note: str | None = None
    source: str
    sort_order: int = 0


class RevisionSnapshot(BaseModel):
    """一个版本的完整快照"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    version: int
    committed_at: datetime
    total_amount: Decimal
    row_count: int
    source_summary: str
    has_attachment: bool = False
    rows: list[RevisionRow] = []


class SupplierHistoryResponse(BaseModel):
    """某供应商在此询价单上的完整调价历史"""
    supplier_id: int
    supplier_code: str
    company_name: str
    inquiry_id: int
    inquiry_code: str
    revisions: list[RevisionSnapshot] = []  # 按 version 升序


# ============== AI 解析返回(不入库) ==============

class ParsedRow(BaseModel):
    """从附件 AI 解析出来的一行,前端会拿到后填 DOM"""
    name: str
    spec: str | None = None
    unit: str = "个"
    qty: Decimal | None = None
    unit_price: Decimal
    note: str | None = None


class ParseAttachmentResult(BaseModel):
    """/parse 端点返回 — 不入库,由前端渲染给供应商校对"""
    ok: bool
    attachment_id: int
    parse_status: str                # done / failed
    parse_note: str | None = None
    rows: list[ParsedRow] = []       # 识别出的行(可能为空)


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


# ============== 公开 magic link 填报(免登录) — 方式4混合模型 ==============

class PublicInquiryItem(BaseModel):
    """方式1兼容:采购员预设的物料(供应商填价)。通常为空。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    spec: str | None = None
    unit: str
    qty: Decimal
    remark: str | None = None
    sort_order: int = 0
    my_unit_price: Decimal | None = None
    my_note: str | None = None


class PublicQuoteRow(BaseModel):
    """供应商自己列的一行报价(名称/规格/单位/数量/单价/备注)"""
    model_config = ConfigDict(from_attributes=True)
    id: int | None = None  # 提交新行 null,更新带 id
    name: str = Field(min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=256)
    unit: str = Field(default="个", max_length=16)
    qty: Decimal | None = None
    unit_price: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=256)
    source: str = "manual"
    sort_order: int = 0


class PublicAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    file_size: int
    mime_type: str
    parse_status: str
    parse_note: str | None = None
    uploaded_at: datetime


class PublicQuoteView(BaseModel):
    """供应商通过 magic link 看到的视图 — 不含任何其他供应商的信息"""
    model_config = ConfigDict(from_attributes=True)
    code: str
    title: str
    remark: str | None = None
    delivery_date: str | None = None
    quote_deadline: datetime | None = None  # 报价截止时间(可空)
    is_expired: bool = False                # 服务端按 now > deadline 计算,前端无需自己判断
    buyer_company_name: str = "湖北欧阳聚德汽车有限公司"
    supplier_company_name: str
    status: InquiryStatus
    created_at: datetime
    quoted_at: datetime | None = None
    preset_items: list[PublicInquiryItem] = []  # 方式1兼容
    rows: list[PublicQuoteRow] = []             # 方式4主数据
    attachments: list[PublicAttachmentRead] = []


class PublicPresetQuote(BaseModel):
    """方式1兼容:针对采购员预设的 InquiryItem 填单价"""
    item_id: int
    unit_price: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=256)


class PublicQuoteSubmit(BaseModel):
    """提交报价 — 覆盖式,传什么就是什么"""
    rows: list[PublicQuoteRow] = Field(default_factory=list)
    preset_quotes: list[PublicPresetQuote] = Field(default_factory=list)
