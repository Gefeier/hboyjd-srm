"""应用配置表 — 通过 HTTP API 动态写入(无需 SSH 改 .env)
存储敏感配置如 LLM API key / 短信 key / 邮件 key 等
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class AppSetting(SQLModel, table=True):
    """key-value 配置表 (singleton per key)"""
    __tablename__ = "app_setting"

    key: str = Field(sa_column=Column(String(64), primary_key=True))
    value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_secret: bool = Field(default=False, sa_column=Column(Integer, nullable=False, server_default="0"))
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )
    updated_by: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
