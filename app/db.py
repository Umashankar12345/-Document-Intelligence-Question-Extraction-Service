from sqlalchemy import create_engine, JSON
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Integer

from app.config import settings

Base = declarative_base()

# Portable JSON (JSONB on PG, JSON on SQLite)
JSONType = JSONB().with_variant(JSON, "sqlite")
IntArray = ARRAY(Integer).with_variant(JSON, "sqlite")


def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
