"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.messages import router as messages_router
from src.api.preferences import router as preferences_router
from src.api.rules import router as rules_router
from src.db import engine
from src.models.orm_models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed default rules on startup."""
    Base.metadata.create_all(bind=engine)
    from src.seed_rules import seed
    seed()
    yield
    # shutdown if needed


app = FastAPI(
    title="Policy-Driven Message Router",
    description="Route messages to channels based on dynamic rules and real-time conditions.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(messages_router)
app.include_router(rules_router)
app.include_router(preferences_router)


@app.get("/health")
def health():
    return {"status": "ok"}
