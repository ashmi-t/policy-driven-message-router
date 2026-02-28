"""Celery application for async message dispatch."""
from celery import Celery
from src.config import settings

app = Celery(
    "message_router",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
    include=["src.tasks"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
app.conf.task_routes = {
    "src.tasks.dispatch_message": {"queue": "dispatch"},
    "src.tasks.process_dlq": {"queue": "dlq"},
}
