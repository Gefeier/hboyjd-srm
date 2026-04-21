from datetime import UTC, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_current_user, require_buyer_or_admin
from app.models.supplier import Supplier, SupplierGrade, SupplierStatus
from app.models.user import User
from app.schemas.supplier import (
    FreezeRequest,
    SupplierListResponse,
    SupplierRead,
    SupplierRegister,
    SupplierRegisterResponse,
    SupplierReviewRequest,
)
from app.security import get_password_hash

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def generate_supplier_code(session: Session) -> str:
    now = datetime.now(UTC)
    day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    day_end = datetime.combine(now.date(), time.max, tzinfo=UTC)
    stmt = select(func.count()).select_from(Supplier).where(Supplier.created_at >= day_start, Supplier.created_at <= day_end)
    count = session.exec(stmt).one()
    return f"SUP{now:%Y%m%d}{count + 1:03d}"


@router.post("/register", response_model=SupplierRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_supplier(payload: SupplierRegister, session: Session = Depends(get_session)) -> SupplierRegisterResponse:
    supplier = Supplier(
        code=generate_supplier_code(session),
        company_name=payload.company_name,
        unified_credit_code=payload.unified_credit_code,
        legal_person=payload.legal_person,
        founded_date=payload.founded_date,
        registered_address=payload.registered_address,
        registered_capital=payload.registered_capital,
        company_type=payload.company_type,
        taxpayer_type=payload.taxpayer_type,
        business_intro=payload.business_intro,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        contact_position=payload.contact_position,
        wechat=payload.wechat,
        landline=payload.landline,
        login_username=payload.login_username or payload.contact_phone,
        login_password_hash=get_password_hash(payload.login_password),
        categories=payload.categories,
        qualifications=payload.qualifications,
    )
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return SupplierRegisterResponse(id=supplier.id, code=supplier.code, status=supplier.status)


@router.get("", response_model=SupplierListResponse)
def list_suppliers(
    status_filter: SupplierStatus | None = Query(default=None, alias="status"),
    grade: SupplierGrade | None = None,
    category: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SupplierListResponse:
    stmt = select(Supplier)
    count_stmt = select(func.count()).select_from(Supplier)
    filters = []
    if status_filter:
        filters.append(Supplier.status == status_filter)
    if grade:
        filters.append(Supplier.grade == grade)
    if category:
        filters.append(Supplier.categories.contains([category]))
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                Supplier.company_name.like(pattern),
                Supplier.unified_credit_code.like(pattern),
                Supplier.contact_name.like(pattern),
                Supplier.code.like(pattern),
            )
        )
    for item in filters:
        stmt = stmt.where(item)
        count_stmt = count_stmt.where(item)
    stmt = stmt.order_by(Supplier.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = session.exec(stmt).all()
    total = session.exec(count_stmt).one()
    return SupplierListResponse(
        items=[SupplierRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SupplierRead:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    return SupplierRead.model_validate(supplier)


@router.post("/{supplier_id}/review", response_model=SupplierRead)
def review_supplier(
    supplier_id: int,
    payload: SupplierReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_buyer_or_admin),
) -> SupplierRead:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    supplier.status = SupplierStatus.APPROVED if payload.action == "approve" else SupplierStatus.REJECTED
    supplier.grade = payload.grade if payload.action == "approve" else None
    supplier.review_note = payload.note
    supplier.reviewed_by = current_user.id
    supplier.reviewed_at = datetime.now(UTC)
    supplier.updated_at = datetime.now(UTC)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return SupplierRead.model_validate(supplier)


@router.post("/{supplier_id}/freeze", response_model=SupplierRead)
def freeze_supplier(
    supplier_id: int,
    payload: FreezeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_buyer_or_admin),
) -> SupplierRead:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    supplier.status = SupplierStatus.FROZEN
    supplier.review_note = payload.note
    supplier.reviewed_by = current_user.id
    supplier.reviewed_at = datetime.now(UTC)
    supplier.updated_at = datetime.now(UTC)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return SupplierRead.model_validate(supplier)
