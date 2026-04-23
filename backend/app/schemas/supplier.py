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
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int


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
