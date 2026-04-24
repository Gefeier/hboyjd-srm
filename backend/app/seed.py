import logging
import os

from sqlmodel import Session, select

import app.db as db_module
from app.models.user import User, UserRole
from app.security import get_password_hash

logger = logging.getLogger(__name__)


def seed_default_user() -> None:
    """首次启动创建默认管理员账号。
    优先使用环境变量 SRM_SEED_PASSWORD,否则用弱密码 ouyang123(仅开发环境用)。
    """
    seed_pwd = os.environ.get("SRM_SEED_PASSWORD", "ouyang123")
    with Session(db_module.engine) as session:
        user = session.exec(select(User).where(User.username == "ouyang")).first()
        if user:
            return
        if seed_pwd == "ouyang123":
            logger.warning(
                "⚠ 首次创建 ouyang 账号使用了默认弱密码,请通过 POST /api/v1/auth/change-password 修改"
            )
        session.add(
            User(
                username="ouyang",
                password_hash=get_password_hash(seed_pwd),
                name="欧阳经理",
                role=UserRole.BUYER,
                phone="13800000000",
                email="buyer@hboyjd.com",
                is_active=True,
            )
        )
        session.commit()


if __name__ == "__main__":
    seed_default_user()
