from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserRole(str, Enum):
    ADMIN = "admin"
    BUYER = "buyer"
    APPROVER = "approver"
    SUPPLIER = "supplier"  # 虚拟角色:实际身份在Supplier表,login返回时合成用


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(32), unique=True, nullable=False, index=True))
    password_hash: str = Field(sa_column=Column(String(256), nullable=False))
    name: str = Field(sa_column=Column(String(64), nullable=False))
    role: UserRole = Field(nullable=False)
    phone: str | None = Field(default=None, sa_column=Column(String(20), nullable=True))
    email: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )
