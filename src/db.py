"""Database engine and session factory."""
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.models.orm_models import Base  # noqa: F401 - registers models with SQLAlchemy

# SQLite needs special handling: no connection pooling, allow multi-thread access
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
