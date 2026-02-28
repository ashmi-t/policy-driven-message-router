"""Async message dispatch. Routes, sends, retries, and moves to DLQ when max retries exceeded."""
import logging
from typing import List

from sqlalchemy.orm import Session

from src.celery_app import app
from src.channels import registry as channel_registry
from src.channels.base import Payload
from src.db import SessionLocal
from src.models.orm_models import (
    Message,
    MessageDelivery,
    MessageLifecycleState,
)
from src.rules.engine import RulesEngine
from src.rules.router import RoutingContext, Router
from src.state import set_delivery_state, set_message_state
from src.templates import get_body_content

logger = logging.getLogger(__name__)


def _get_routing_decision(db: Session, message: Message) -> tuple:
    engine = RulesEngine(db)
    router = Router(engine)
    ctx = RoutingContext(
        user_id=message.recipient_id,
        message_type=message.message_type,
        priority=message.priority,
        recipient_email=message.recipient_email,
        recipient_phone=message.recipient_phone,
        extra=message.metadata_ or {},
    )
    decision = router.route(ctx)
    return decision.channels, decision.fallback_channels, decision.max_retries


def _create_delivery(db: Session, message_id: int, channel: str, max_retries: int) -> MessageDelivery:
    d = MessageDelivery(
        message_id=message_id,
        channel=channel,
        state=MessageLifecycleState.QUEUED.value,
        max_retries=max_retries,
    )
    db.add(d)
    db.flush()
    return d


def _send_one(db: Session, message: Message, delivery: MessageDelivery) -> bool:
    channel = channel_registry.get_available(delivery.channel)
    if not channel:
        delivery.last_error = "Channel not available"
        set_delivery_state(db, delivery, MessageLifecycleState.FAILED.value)
        return False
    body = get_body_content(message.body_template, message.body_context or {})
    recipient = message.recipient_email if delivery.channel == "email" else message.recipient_phone
    if not recipient:
        delivery.last_error = "Missing recipient"
        set_delivery_state(db, delivery, MessageLifecycleState.FAILED.value)
        return False
    payload = Payload(recipient=recipient, subject=message.subject, body=body)
    result = channel.send(payload)
    if result.success:
        delivery.provider_id = result.provider_id
        set_delivery_state(db, delivery, MessageLifecycleState.DELIVERED.value)
        return True
    delivery.last_error = result.error
    set_delivery_state(db, delivery, MessageLifecycleState.FAILED.value)
    return False


@app.task(bind=True, max_retries=0)
def dispatch_message(self, message_id: int) -> None:
    db = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.warning("Message %s not found", message_id)
            return
        if message.state != MessageLifecycleState.QUEUED.value:
            return

        set_message_state(db, message, MessageLifecycleState.DISPATCHING.value)
        db.commit()

        db = SessionLocal()
        message = db.query(Message).filter(Message.id == message_id).first()
        channels, fallback_channels, max_retries = _get_routing_decision(db, message)
        if not channels:
            channels = fallback_channels
        if not channels:
            message.state = MessageLifecycleState.FAILED.value
            message.metadata_ = (message.metadata_ or {}) | {"failure_reason": "no_channels"}
            db.commit()
            return

        # Use IDs instead of ORM objects—session closes after commit, objects detach
        delivery_ids: list[int] = []
        for ch in channels:
            d = _create_delivery(db, message.id, ch, max_retries)
            delivery_ids.append(d.id)
        db.commit()

        any_success = False
        for delivery_id in delivery_ids:
            db = SessionLocal()
            d = db.query(MessageDelivery).filter(MessageDelivery.id == delivery_id).first()
            m = db.query(Message).filter(Message.id == message_id).first()
            if not d or not m:
                continue
            set_delivery_state(db, d, MessageLifecycleState.DISPATCHING.value)
            db.commit()
            ok = _send_one(db, m, d)
            db.commit()
            if ok:
                any_success = True

        db = SessionLocal()
        message = db.query(Message).filter(Message.id == message_id).first()
        if any_success:
            set_message_state(db, message, MessageLifecycleState.DELIVERED.value)
            db.commit()
            return

        for ch in fallback_channels:
            if ch in [d.channel for d in message.deliveries]:
                continue
            fd = _create_delivery(db, message.id, ch, max_retries)
            delivery_id = fd.id
            db.commit()
            db = SessionLocal()
            d = db.query(MessageDelivery).filter(MessageDelivery.id == delivery_id).first()
            m = db.query(Message).filter(Message.id == message_id).first()
            set_delivery_state(db, d, MessageLifecycleState.DISPATCHING.value)
            db.commit()
            if _send_one(db, m, d):
                set_message_state(db, m, MessageLifecycleState.DELIVERED.value)
                db.commit()
                return
            db.commit()

        db = SessionLocal()
        message = db.query(Message).filter(Message.id == message_id).first()
        current_retries = max((delivery.retry_count for delivery in message.deliveries), default=0)
        if current_retries < max_retries:
            message.state = MessageLifecycleState.QUEUED.value
            for d in message.deliveries:
                d.retry_count = current_retries + 1
            db.commit()
            dispatch_message.apply_async(args=[message_id], countdown=60)
        else:
            set_message_state(db, message, MessageLifecycleState.DLQ.value)
            db.commit()
    except Exception as e:
        logger.exception("dispatch_message failed for message_id=%s", message_id)
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()
