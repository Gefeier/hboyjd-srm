"""物料主档(Material) — 用过即归档,采购员下次可一键复用

设计原则:
- 不需要事先维护一份物料台账。每次新建询价单提交时,后端自动 upsert Material
  (按 name + spec 匹配,匹配上则 use_count+1 / last_used_at 刷新; 不匹配则新建)。
- 查询时按 last_used_at desc + use_count desc 排序,采购员搜出来的就是
  "最近最常用"的物料。
- 不存价格、不存数量(那是 InquiryItem 的事)。
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Material(SQLModel, table=True):
    __tablename__ = "material"
    __table_args__ = (
        # 查询常用组合:大类 + 最近使用
        Index("ix_material_category_last_used", "category", "last_used_at"),
        # 名称模糊搜索时, name 已建索引可加速 LIKE 'xxx%' 模式
        Index("ix_material_name", "name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(128), nullable=False))
    spec: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    unit: str = Field(default="个", sa_column=Column(String(16), nullable=False))
    category: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))

    # 使用统计
    use_count: int = Field(default=1, sa_column=Column(Integer, nullable=False, server_default="1"))
    last_used_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    # 最近一次用此物料的人(便于采购主管追踪)
    last_used_buyer_id: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    )
