"""Database session and engine."""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.models.orm_models import Base  # noqa: F401 - ensure models registered

_connect_args = {}
_pool_class = None
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    from sqlalchemy.pool import StaticPool
    _pool_class = StaticPool

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    poolclass=_pool_class,
    pool_pre_ping=not settings.database_url.startswith("sqlite"),
    echo=bool(os.getenv("SQL_ECHO")),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
