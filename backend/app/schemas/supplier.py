import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.supplier import SupplierGrade, SupplierSource, SupplierStatus, TaxpayerType

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class SupplierSimpleRegister(BaseModel):
    """最简注册:手机号+密码+公司名。其他资料登录后在'完善资料'里补"""
    company_name: str = Field(min_length=2, max_length=128)
    contact_phone: str
    login_password: str

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_PATTERN.match(value):
            raise ValueError("请填写 11 位大陆手机号")
        return value

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("login_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码至少 8 位")
        return value


class SupplierProfileUpdate(BaseModel):
    """资料补全/修改:除了手机号和公司名其余都能改"""
    unified_credit_code: str | None = Field(default=None, min_length=18, max_length=18)
    legal_person: str | None = None
    founded_date: date | None = None
    registered_address: str | None = None
    registered_capital: Decimal | None = None
    company_type: str | None = None
    taxpayer_type: TaxpayerType | None = None
    business_intro: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_position: str | None = None
    wechat: str | None = None
    landline: str | None = None
    categories: list[str] | None = None
    qualifications: list[dict] | None = None
    submit_for_review: bool = False  # true=提交审核 status→pending

    @field_validator("contact_email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("新密码至少 8 位")
        return value


class SupplierSimpleRegisterResponse(BaseModel):
    id: int
    code: str
    status: SupplierStatus
    login_username: str
    access_token: str  # 注册成功顺便签发token,免二次登录
    token_type: str = "bearer"


class AdminCreateSupplier(BaseModel):
    """采购员手工开账号(为老/离线供应商)"""
    company_name: str = Field(min_length=2, max_length=128)
    contact_phone: str
    login_password: str | None = None  # 不传则后端生成

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_PATTERN.match(value):
            raise ValueError("请填写 11 位大陆手机号")
        return value

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, value: str) -> str:
        return value.strip()


class AdminCreateSupplierResponse(BaseModel):
    """返回包含明文密码,便于采购员一次性告知供应商"""
    id: int
    code: str
    company_name: str
    login_username: str
    login_password: str  # 明文仅在创建时返回
    status: SupplierStatus


# 保留旧的完整注册 schema 以免 break(采购员手工建档还会用)
class SupplierRegister(BaseModel):
    company_name: str
    unified_credit_code: str = Field(min_length=18, max_length=18)
    legal_person: str
    founded_date: date | None = None
    registered_address: str | None = None
    registered_capital: Decimal | None = None
    company_type: str | None = None
    taxpayer_type: TaxpayerType | None = None
    business_intro: str | None = None
    contact_name: str
    contact_phone: str
    contact_email: str
    contact_position: str | None = None
    wechat: str | None = None
    landline: str | None = None
    login_username: str | None = None
    login_password: str
    categories: list[str] = Field(default_factory=list)
    qualifications: list[dict] = Field(default_factory=list)

    @field_validator("login_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码至少 8 位")
        return value

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def fill_login_username(self):
        if not self.login_username:
            self.login_username = self.contact_phone
        return self


class SupplierRegisterResponse(BaseModel):
    id: int
    code: str
    status: SupplierStatus


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    company_name: str
    contact_phone: str
    login_username: str
    unified_credit_code: str | None = None
    legal_person: str | None = None
    founded_date: date | None = None
    registered_address: str | None = None
    registered_capital: Decimal | None = None
    company_type: str | None = None
    taxpayer_type: TaxpayerType | None = None
    business_intro: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_position: str | None = None
    wechat: str | None = None
    landline: str | None = None
    status: SupplierStatus
    source: SupplierSource = SupplierSource.SELF_REGISTER
    profile_completed: bool = False
    grade: SupplierGrade | None = None
    review_note: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    categories: list[str]
    qualifications: list[dict]
    excluded_from_rfq: bool = False
    excluded_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int


class SupplierAdminUpdate(BaseModel):
    """采购主管端编辑 — 改物料分类 tag、不参与询价开关。
    所有字段都是可选(unset 不动);传空列表会清空 tag。"""
    categories: list[str] | None = None
    excluded_from_rfq: bool | None = None
    excluded_reason: str | None = Field(default=None, max_length=64)


class MaterialCategoryItem(BaseModel):
    name: str
    hint: str = ""


class MaterialCategoryListResponse(BaseModel):
    items: list[MaterialCategoryItem]


# ============== 金蝶批量导入 ==============

class BatchImportItem(BaseModel):
    """单条导入数据 — 来源金蝶 BD_Supplier + 草稿tag(基于采购历史聚类)"""
    company_name: str = Field(min_length=2, max_length=128)
    contact_phone: str | None = None  # 金蝶很多供应商无电话字段,可空
    contact_name: str | None = None
    unified_credit_code: str | None = None
    registered_address: str | None = None
    categories: list[str] = []  # 草稿 tag(本地脚本基于历史采购聚类得出)
    kingdee_no: str | None = None  # 金蝶供应商编号(冗余记录用,如 VEN00109)


class BatchImportRequest(BaseModel):
    items: list[BatchImportItem] = Field(min_length=1, max_length=500)
    skip_if_categories_exist: bool = True  # 默认:已有 tag 的不动(避免覆盖人工修改)


class BatchImportItemResult(BaseModel):
    company_name: str
    action: str  # created / updated_categories / skipped
    supplier_id: int | None = None
    code: str | None = None
    note: str | None = None
    categories: list[str] = []


class BatchImportResponse(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    items: list[BatchImportItemResult]


class SupplierReviewRequest(BaseModel):
    action: str
    note: str | None = None
    grade: SupplierGrade | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in {"approve", "reject"}:
            raise ValueError("action 只允许 approve 或 reject")
        return value

    @model_validator(mode="after")
    def validate_grade(self):
        if self.action == "approve" and not self.grade:
            raise ValueError("审核通过时必须填写 grade")
        return self


class FreezeRequest(BaseModel):
    note: str
