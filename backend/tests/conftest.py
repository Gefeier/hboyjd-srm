import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

os.environ["DATABASE_URL"] = "sqlite:///./bootstrap-test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.config import get_settings  # noqa: E402
from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.security import get_password_hash  # noqa: E402
import app.db as db_module  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    get_settings.cache_clear()
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    db_module.engine = engine

    with Session(engine) as session:
        session.add(
            User(
                username="ouyang",
                password_hash=get_password_hash("ouyang123"),
                name="欧阳俊丽",
                role=UserRole.BUYER,
                phone="13800000000",
                email="ouyang@example.com",
                is_active=True,
            )
        )
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
