from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlmodel import Session, select

from app.db import get_session
from app.models.user import User, UserRole
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
    except JWTError as exc:
        raise credentials_error from exc
    if not subject:
        raise credentials_error
    user = session.exec(select(User).where(User.username == subject, User.is_active.is_(True))).first()
    if not user:
        raise credentials_error
    return user


def require_buyer_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.BUYER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有审核权限")
    return current_user
