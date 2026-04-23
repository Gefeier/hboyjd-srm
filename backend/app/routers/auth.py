from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_current_user
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.user import LoginRequest, LoginResponse, UserRead
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _supplier_as_user(sup: Supplier) -> UserRead:
    """把 Supplier 伪装成 UserRead,返回给前端用同一套token/rbac机制"""
    return UserRead(
        id=sup.id,
        username=sup.login_username,
        name=sup.contact_name or sup.company_name,
        role=UserRole.SUPPLIER,
        phone=sup.contact_phone,
        email=sup.contact_email,
        is_active=True,
        created_at=sup.created_at,
        updated_at=sup.updated_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    # 1. 先查内部User(采购员/管理员/审批)
    user = session.exec(select(User).where(User.username == payload.username, User.is_active.is_(True))).first()
    if user and verify_password(payload.password, user.password_hash):
        access_token = create_access_token(user.username, role=str(user.role))
        return LoginResponse(access_token=access_token, user=UserRead.model_validate(user))

    # 2. 再查Supplier表(按login_username匹配)
    sup = session.exec(select(Supplier).where(Supplier.login_username == payload.username)).first()
    if sup and verify_password(payload.password, sup.login_password_hash):
        access_token = create_access_token(sup.login_username, role=str(UserRole.SUPPLIER), supplier_id=sup.id)
        return LoginResponse(access_token=access_token, user=_supplier_as_user(sup))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
