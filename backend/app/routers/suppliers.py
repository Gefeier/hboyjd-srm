from datetime import UTC, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.constants import MATERIAL_CATEGORIES, MATERIAL_CATEGORY_HINTS
from app.db import get_session
from app.deps import get_current_user, require_buyer_or_admin
from app.models.supplier import Supplier, SupplierGrade, SupplierSource, SupplierStatus
from app.models.user import User, UserRole
from app.schemas.supplier import (
    AdminCreateSupplier,
    AdminCreateSupplierResponse,
    ChangePasswordRequest,
    FreezeRequest,
    MaterialCategoryItem,
    MaterialCategoryListResponse,
    SupplierAdminUpdate,
    SupplierListResponse,
    SupplierProfileUpdate,
    SupplierRead,
    SupplierRegister,
    SupplierRegisterResponse,
    SupplierReviewRequest,
    SupplierSimpleRegister,
    SupplierSimpleRegisterResponse,
)
from app.security import create_access_token, decode_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def current_supplier(session: Session = Depends(get_session), token: str = Depends(_oauth2)) -> Supplier:
    """从JWT token解出supplier身份;专供供应商登录后自查/报价等接口"""
    cred_err = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效,请重新登录")
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise cred_err
    if payload.get("role") != "supplier":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要供应商登录")
    sup = None
    sup_id = payload.get("supplier_id")
    if sup_id:
        sup = session.get(Supplier, sup_id)
    if not sup:
        username = payload.get("sub")
        if username:
            sup = session.exec(select(Supplier).where(Supplier.login_username == username)).first()
    if not sup:
        raise cred_err
    return sup


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


@router.post("/admin-create", response_model=AdminCreateSupplierResponse, status_code=status.HTTP_201_CREATED)
def admin_create_supplier(
    payload: AdminCreateSupplier,
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> AdminCreateSupplierResponse:
    """采购员手工给供应商建账号(source=manual)。可指定密码或由后端生成。
    明文密码一次性返回给采购员,便于线下转告供应商。"""
    import secrets, string

    existing_phone = session.exec(select(Supplier).where(Supplier.contact_phone == payload.contact_phone)).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="此手机号已被占用")
    existing_name = session.exec(select(Supplier).where(Supplier.company_name == payload.company_name)).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="此企业名称已存在")

    # 生成密码(若未指定)
    if payload.login_password:
        plain_password = payload.login_password
    else:
        # 8 位:2 字母 + 6 数字,好记好念
        alpha = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(2))
        digits = ''.join(secrets.choice(string.digits) for _ in range(6))
        plain_password = alpha + digits

    supplier = Supplier(
        code=generate_supplier_code(session),
        company_name=payload.company_name,
        contact_phone=payload.contact_phone,
        login_username=payload.contact_phone,
        login_password_hash=get_password_hash(plain_password),
        status=SupplierStatus.PENDING_PROFILE,
        source=SupplierSource.MANUAL,
    )
    session.add(supplier)
    session.commit()
    session.refresh(supplier)

    return AdminCreateSupplierResponse(
        id=supplier.id,
        code=supplier.code,
        company_name=supplier.company_name,
        login_username=supplier.login_username,
        login_password=plain_password,
        status=supplier.status,
    )


@router.post("/simple-register", response_model=SupplierSimpleRegisterResponse, status_code=status.HTTP_201_CREATED)
def simple_register(payload: SupplierSimpleRegister, session: Session = Depends(get_session)) -> SupplierSimpleRegisterResponse:
    """最简注册:手机号+密码+公司名 → 创建pending_profile状态账号,签发token免二次登录"""
    # 防重:手机号或公司名任一已存在都拒绝
    existing_phone = session.exec(select(Supplier).where(Supplier.contact_phone == payload.contact_phone)).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="此手机号已注册,请直接登录或修改密码")
    existing_name = session.exec(select(Supplier).where(Supplier.company_name == payload.company_name)).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="此企业名称已注册")

    supplier = Supplier(
        code=generate_supplier_code(session),
        company_name=payload.company_name,
        contact_phone=payload.contact_phone,
        login_username=payload.contact_phone,  # 默认手机号=用户名
        login_password_hash=get_password_hash(payload.login_password),
        status=SupplierStatus.PENDING_PROFILE,
        source=SupplierSource.SELF_REGISTER,
    )
    session.add(supplier)
    session.commit()
    session.refresh(supplier)

    access_token = create_access_token(supplier.login_username, role=str(UserRole.SUPPLIER), supplier_id=supplier.id)
    return SupplierSimpleRegisterResponse(
        id=supplier.id,
        code=supplier.code,
        status=supplier.status,
        login_username=supplier.login_username,
        access_token=access_token,
    )


@router.get("/me", response_model=SupplierRead)
def get_my_supplier(sup: Supplier = Depends(current_supplier)) -> SupplierRead:
    """供应商拉自己的档案(含审核状态/等级/品类)"""
    return SupplierRead.model_validate(sup)


@router.patch("/me", response_model=SupplierRead)
def update_my_profile(
    payload: SupplierProfileUpdate,
    sup: Supplier = Depends(current_supplier),
    session: Session = Depends(get_session),
) -> SupplierRead:
    """供应商自己补全/修改资料。若submit_for_review=true且资料齐全,状态 pending_profile→pending"""
    data = payload.model_dump(exclude_unset=True, exclude={"submit_for_review"})
    for k, v in data.items():
        setattr(sup, k, v)
    sup.updated_at = datetime.now(UTC)

    if payload.submit_for_review:
        if not sup.profile_completed:
            raise HTTPException(status_code=400, detail="资料未填齐,无法提交审核。请补全公司信息/联系人/品类")
        # 仅允许从 pending_profile 和 rejected 进入 pending
        if sup.status in (SupplierStatus.PENDING_PROFILE, SupplierStatus.REJECTED):
            sup.status = SupplierStatus.PENDING
            sup.review_note = None  # 清掉旧的驳回意见

    session.add(sup)
    session.commit()
    session.refresh(sup)
    return SupplierRead.model_validate(sup)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: ChangePasswordRequest,
    sup: Supplier = Depends(current_supplier),
    session: Session = Depends(get_session),
) -> None:
    """供应商修改密码"""
    if not verify_password(payload.old_password, sup.login_password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    sup.login_password_hash = get_password_hash(payload.new_password)
    sup.updated_at = datetime.now(UTC)
    session.add(sup)
    session.commit()


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


@router.get("/_categories", response_model=MaterialCategoryListResponse)
def list_material_categories(_: User = Depends(get_current_user)) -> MaterialCategoryListResponse:
    """SRM 物料大类列表 — 11 个比价范围内的固定分类。前端勾选/筛选用。"""
    return MaterialCategoryListResponse(
        items=[
            MaterialCategoryItem(name=c, hint=MATERIAL_CATEGORY_HINTS.get(c, ""))
            for c in MATERIAL_CATEGORIES
        ]
    )


@router.patch("/{supplier_id}/admin", response_model=SupplierRead)
def admin_update_supplier(
    supplier_id: int,
    payload: SupplierAdminUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_buyer_or_admin),
) -> SupplierRead:
    """采购主管/采购员编辑供应商分类 tag 与"是否参与询价"开关。"""
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="未提供任何修改内容")

    if "categories" in data:
        # 校验 — 落地的 tag 必须在 11 大类内(防前端误传/接口被滥用)
        cats = data["categories"] or []
        invalid = [c for c in cats if c not in MATERIAL_CATEGORIES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"无效的物料分类: {invalid}。请使用预定义的 11 个大类。",
            )
        # 去重保序
        supplier.categories = list(dict.fromkeys(cats))

    if "excluded_from_rfq" in data:
        supplier.excluded_from_rfq = bool(data["excluded_from_rfq"])
        if not supplier.excluded_from_rfq:
            supplier.excluded_reason = None  # 取消排除时清掉理由

    if "excluded_reason" in data:
        supplier.excluded_reason = (data["excluded_reason"] or "").strip() or None

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
