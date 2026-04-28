"""物料主档 — 采购员搜索/选择历史用过的物料"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.constants import MATERIAL_CATEGORIES
from app.db import get_session
from app.deps import get_current_user
from app.models.material import Material
from app.models.user import User
from app.schemas.material import MaterialListResponse, MaterialRead

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("/_categories")
def list_categories() -> dict[str, list[str]]:
    """前端拉取大类列表用 — 与 /suppliers/_categories 对齐"""
    return {"categories": MATERIAL_CATEGORIES}


@router.get("", response_model=MaterialListResponse)
def list_materials(
    q: str | None = Query(default=None, description="按名称/规格模糊搜索"),
    category: str | None = Query(default=None, description="11大类之一"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> MaterialListResponse:
    stmt = select(Material)
    count_stmt = select(func.count()).select_from(Material)

    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Material.name.like(pattern), Material.spec.like(pattern)))
    if category:
        filters.append(Material.category == category)
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    # 排序:最近用过的在前、用得多的在前
    stmt = stmt.order_by(
        Material.last_used_at.desc(),
        Material.use_count.desc(),
    ).offset((page - 1) * page_size).limit(page_size)

    rows = session.exec(stmt).all()
    total = session.exec(count_stmt).one()
    return MaterialListResponse(
        items=[MaterialRead.model_validate(m) for m in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def upsert_material(
    session: Session,
    *,
    name: str,
    spec: str | None,
    unit: str,
    category: str | None,
    buyer_id: int | None = None,
) -> Material:
    """创建/更新询价物料行时调用 — 自动入物料主档

    匹配规则:name 精确 + spec 精确(NULL 视作 NULL 同等)。命中则 use_count+1
    并刷新 last_used_at;否则新建。
    """
    name_clean = name.strip()
    spec_clean = spec.strip() if isinstance(spec, str) and spec.strip() else None

    stmt = select(Material).where(Material.name == name_clean)
    if spec_clean is None:
        stmt = stmt.where(Material.spec.is_(None))
    else:
        stmt = stmt.where(Material.spec == spec_clean)

    existing = session.exec(stmt).first()
    now = datetime.now(tz=None).astimezone()  # naive vs aware: 用本地 aware

    if existing:
        existing.use_count = (existing.use_count or 0) + 1
        existing.last_used_at = now
        if category and category in MATERIAL_CATEGORIES:
            existing.category = category  # 后填的 category 覆盖空值/旧值
        if unit and unit != existing.unit:
            existing.unit = unit
        if buyer_id:
            existing.last_used_buyer_id = buyer_id
        session.add(existing)
        return existing

    cat = category if category in MATERIAL_CATEGORIES else None
    m = Material(
        name=name_clean,
        spec=spec_clean,
        unit=unit or "个",
        category=cat,
        use_count=1,
        last_used_at=now,
        last_used_buyer_id=buyer_id,
    )
    session.add(m)
    session.flush()
    return m
