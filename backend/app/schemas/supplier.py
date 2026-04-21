import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.supplier import SupplierGrade, SupplierStatus, TaxpayerType

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


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
        if not PASSWORD_PATTERN.match(value):
            raise ValueError("密码至少 8 位，且必须包含字母和数字")
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
    unified_credit_code: str
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
    login_username: str
    status: SupplierStatus
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
