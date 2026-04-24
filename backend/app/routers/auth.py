from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_current_user
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.user import LoginRequest, LoginResponse, UserRead
from app.security import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# 登录防爆破:用 Redis 做计数器
MAX_FAIL = 5
LOCK_SECONDS = 30 * 60  # 30分钟
FAIL_WINDOW = 15 * 60   # 15分钟内累计


def _get_redis(request: Request):
    return getattr(request.app.state, "redis", None)


def _fail_key(username: str) -> str:
    # 按用户名+ IP 粒度都行,先用 username 防止某个账号被打爆
    return f"srm:login_fail:{username.lower().strip()}"


def _check_locked(request: Request, username: str) -> None:
    r = _get_redis(request)
    if not r:
        return  # Redis 不可用就降级放行(不打断业务)
    try:
        val = r.get(_fail_key(username))
        if val and int(val) >= MAX_FAIL:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录失败次数过多,账号已临时锁定 30 分钟,请稍后再试或联系管理员",
            )
    except HTTPException:
        raise
    except Exception:
        return


def _record_fail(request: Request, username: str) -> None:
    r = _get_redis(request)
    if not r:
        return
    try:
        key = _fail_key(username)
        n = r.incr(key)
        if n == 1:
            r.expire(key, FAIL_WINDOW)
        if int(n) >= MAX_FAIL:
            r.expire(key, LOCK_SECONDS)
    except Exception:
        return


def _clear_fail(request: Request, username: str) -> None:
    r = _get_redis(request)
    if not r:
        return
    try:
        r.delete(_fail_key(username))
    except Exception:
        return


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
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_session)) -> LoginResponse:
    # 防爆破:先检查是否已锁
    _check_locked(request, payload.username)

    # 1. 先查内部User(采购员/管理员/审批)
    user = session.exec(select(User).where(User.username == payload.username, User.is_active.is_(True))).first()
    if user and verify_password(payload.password, user.password_hash):
        _clear_fail(request, payload.username)
        access_token = create_access_token(user.username, role=str(user.role))
        return LoginResponse(access_token=access_token, user=UserRead.model_validate(user))

    # 2. 再查Supplier表(按login_username匹配)
    sup = session.exec(select(Supplier).where(Supplier.login_username == payload.username)).first()
    if sup and verify_password(payload.password, sup.login_password_hash):
        _clear_fail(request, payload.username)
        access_token = create_access_token(sup.login_username, role=str(UserRole.SUPPLIER), supplier_id=sup.id)
        return LoginResponse(access_token=access_token, user=_supplier_as_user(sup))

    # 失败 → 计数 +1
    _record_fail(request, payload.username)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


class ChangeMyPasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("新密码至少 8 位")
        # 弱密码黑名单
        banned = {"ouyang123", "12345678", "password", "admin123", "qwerty12"}
        if v.lower() in banned:
            raise ValueError("密码过于简单,请换一个")
        if v.isdigit() or v.isalpha():
            raise ValueError("密码需要同时包含字母和数字")
        return v


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: ChangeMyPasswordRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """内部用户(采购员/管理员)改自己的密码"""
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    current_user.password_hash = get_password_hash(payload.new_password)
    session.add(current_user)
    session.commit()
