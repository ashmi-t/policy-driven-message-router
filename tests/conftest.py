"""Pytest fixtures: in-memory DB, test client, sample data."""
import os
from typing import Generator

# Force test DB before any src import
os.environ["DATABASE_URL"] = "sqlite:///:memory:?check_same_thread=0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.db import SessionLocal, engine
from src.main import app
from src.models.orm_models import Base


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    from src.db import get_db
    def get_db_override():
        yield db
    app.dependency_overrides[get_db] = get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
