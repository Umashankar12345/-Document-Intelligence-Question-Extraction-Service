import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Configure test database file path before importing app modules
TEST_STORAGE = Path("./data/test_storage").resolve()
TEST_DB_FILE = Path("./data/test_pragati.db").resolve()
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE}"

settings.database_url = TEST_DB_URL
settings.celery_task_always_eager = 1
settings.storage_root = str(TEST_STORAGE)

from app.db import Base, engine, SessionLocal, get_db, init_db
from app.main import app
from app.models import User
from app.auth import get_password_hash, create_access_token


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    TEST_STORAGE.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup after all tests
    if TEST_DB_FILE.exists():
        try:
            TEST_DB_FILE.unlink()
        except Exception:
            pass


@pytest.fixture(scope="function")
def db_session():
    # Re-create tables cleanly for each test function
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def normal_user(db_session) -> User:
    user = User(
        email="testuser@pragati.edu",
        password_hash=get_password_hash("Password123!"),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session) -> User:
    user = User(
        email="otheruser@pragati.edu",
        password_hash=get_password_hash("Password123!"),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session) -> User:
    admin = User(
        email="admin@pragati.edu",
        password_hash=get_password_hash("AdminPass123!"),
        role="admin",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def user_token(normal_user) -> str:
    return create_access_token(data={"sub": normal_user.id, "role": normal_user.role, "email": normal_user.email})


@pytest.fixture
def other_token(other_user) -> str:
    return create_access_token(data={"sub": other_user.id, "role": other_user.role, "email": other_user.email})


@pytest.fixture
def admin_token(admin_user) -> str:
    return create_access_token(data={"sub": admin_user.id, "role": admin_user.role, "email": admin_user.email})


@pytest.fixture
def user_headers(user_token) -> dict:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def other_headers(other_token) -> dict:
    return {"Authorization": f"Bearer {other_token}"}


@pytest.fixture
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
