from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    spec: str | None = None
    unit: str
    category: str | None = None
    use_count: int
    last_used_at: datetime


class MaterialListResponse(BaseModel):
    items: list[MaterialRead]
    total: int
    page: int
    page_size: int
