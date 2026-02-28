"""Tests for retry behavior and DLQ."""
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.models.orm_models import (
    Message,
    MessageLifecycleState,
    RoutingRule,
)
from src.tasks import dispatch_message


@pytest.fixture
def db_with_retry_rule(db: Session) -> None:
    """Rule with max_retries=2 (allows 2 retries before DLQ)."""
    db.add(
        RoutingRule(
            name="Email with retry",
            priority_order=0,
            active=True,
            conditions={"message_types": ["promotion"]},
            channels=["email"],
            fallback_channels=[],
            max_retries=2,
        )
    )
    db.commit()


def test_retry_count_increments_on_failure(db: Session, db_with_retry_rule: None) -> None:
    """When send fails, retry_count increments and message stays QUEUED for retry."""
    msg = Message(
        message_type="promotion",
        priority="normal",
        body_template="Hi",
        body_context={},
        recipient_id="user1",
        recipient_email="user@example.com",
        state=MessageLifecycleState.QUEUED.value,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    with patch("src.tasks.dispatch_message.apply_async"), patch(
        "src.tasks.channel_registry"
    ) as mock_registry:
        mock_registry.get_available.return_value = None  # Channel not configured
        dispatch_message.apply(args=[msg.id])

    session = SessionLocal()
    msg = session.query(Message).filter(Message.id == msg.id).first()
    assert msg.state == MessageLifecycleState.QUEUED.value
    assert len(msg.deliveries) == 1
    assert msg.deliveries[0].retry_count == 1
    assert msg.deliveries[0].last_error == "Channel not available"
    session.close()


def test_message_moves_to_dlq_after_max_retries(db: Session, db_with_retry_rule: None) -> None:
    """After max_retries failures, message moves to DLQ."""
    msg = Message(
        message_type="promotion",
        priority="normal",
        body_template="Hi",
        body_context={},
        recipient_id="user1",
        recipient_email="user@example.com",
        state=MessageLifecycleState.QUEUED.value,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    message_id = msg.id

    with patch("src.tasks.dispatch_message.apply_async"), patch(
        "src.tasks.channel_registry"
    ) as mock_registry:
        mock_registry.get_available.return_value = None  # Channel not configured
        # Run 1: fail -> retry_count=1, re-queued
        dispatch_message.apply(args=[message_id])
        # Run 2: fail -> retry_count=2, re-queued
        dispatch_message.apply(args=[message_id])
        # Run 3: fail -> retry_count (2) >= max_retries (2) -> DLQ
        dispatch_message.apply(args=[message_id])

    session = SessionLocal()
    msg = session.query(Message).filter(Message.id == message_id).first()
    assert msg.state == MessageLifecycleState.DLQ.value
    assert msg.deliveries[0].retry_count == 2
    session.close()
