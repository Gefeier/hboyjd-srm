from sqlmodel import Session, select

import app.db as db_module
from app.models.user import User, UserRole
from app.security import get_password_hash


def seed_default_user() -> None:
    with Session(db_module.engine) as session:
        user = session.exec(select(User).where(User.username == "ouyang")).first()
        if user:
            return
        session.add(
            User(
                username="ouyang",
                password_hash=get_password_hash("ouyang123"),
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
