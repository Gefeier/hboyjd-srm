"""管理员配置 API — 通过 HTTP 写入敏感配置(无需 SSH)

LLM key / 短信 key / 邮件 key 等都走这里。
读取时带 mask;写入只允许 admin 角色。
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.deps import require_buyer_or_admin
from app.models.app_setting import AppSetting
from app.models.user import User

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])

# 已知的敏感 key 名(写入时自动标记 is_secret)
SECRET_KEYS = {
    "MINIMAX_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "ALIYUN_SMS_KEY", "ALIYUN_SMS_SECRET",
    "DINGTALK_WEBHOOK_SECRET",
}

# 允许写入的 key 白名单(防止瞎设)
ALLOWED_KEYS = SECRET_KEYS | {
    "MINIMAX_BASE_URL", "MINIMAX_MODEL", "MINIMAX_VISION_MODEL",
    "ALIYUN_SMS_TEMPLATE", "ALIYUN_SMS_SIGN",
    "DINGTALK_WEBHOOK_URL",
    "PLATFORM_NAME", "PLATFORM_PHONE", "PLATFORM_ADDRESS",
}


def mask_value(v: str | None, is_secret: bool) -> str | None:
    """敏感值只显示前4 + 后4,中间 ***"""
    if not v:
        return v
    if not is_secret:
        return v
    if len(v) <= 10:
        return "*" * len(v)
    return v[:4] + "*" * (len(v) - 8) + v[-4:]


class SettingRead(BaseModel):
    key: str
    value: str | None
    is_secret: bool
    updated_at: datetime
    updated_by: int | None = None


class SettingUpdate(BaseModel):
    value: str | None  # null = 删除该 key


@router.get("", response_model=list[SettingRead])
def list_settings(
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> list[SettingRead]:
    rows = session.exec(select(AppSetting).order_by(AppSetting.key)).all()
    return [
        SettingRead(
            key=r.key,
            value=mask_value(r.value, r.is_secret),
            is_secret=r.is_secret,
            updated_at=r.updated_at,
            updated_by=r.updated_by,
        )
        for r in rows
    ]


@router.put("/{key}", response_model=SettingRead)
def upsert_setting(
    key: str,
    payload: SettingUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_buyer_or_admin),
) -> SettingRead:
    if key not in ALLOWED_KEYS:
        raise HTTPException(400, f"不允许的 key: {key}。允许列表见 ALLOWED_KEYS。")

    is_secret = key in SECRET_KEYS
    rec = session.get(AppSetting, key)
    if rec is None:
        rec = AppSetting(
            key=key,
            value=payload.value,
            is_secret=is_secret,
            updated_by=current_user.id,
        )
        session.add(rec)
    else:
        rec.value = payload.value
        rec.is_secret = is_secret
        rec.updated_at = datetime.now(UTC)
        rec.updated_by = current_user.id
        session.add(rec)
    session.commit()
    session.refresh(rec)
    return SettingRead(
        key=rec.key,
        value=mask_value(rec.value, rec.is_secret),
        is_secret=rec.is_secret,
        updated_at=rec.updated_at,
        updated_by=rec.updated_by,
    )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    key: str,
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> None:
    rec = session.get(AppSetting, key)
    if rec:
        session.delete(rec)
        session.commit()
