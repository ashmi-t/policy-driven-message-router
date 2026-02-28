"""Tests for message lifecycle state machine."""
import os
import pytest

# Use SQLite for state tests
os.environ["DATABASE_URL"] = "sqlite:///:memory:?check_same_thread=0"

from src.db import SessionLocal, engine
from src.models.orm_models import Base, Message, MessageDelivery, MessageLifecycleState
from src.state import can_transition, set_message_state, set_delivery_state


@pytest.fixture
def db_state():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_valid_transitions() -> None:
    assert can_transition(MessageLifecycleState.PENDING.value, MessageLifecycleState.QUEUED.value) is True
    assert can_transition(MessageLifecycleState.QUEUED.value, MessageLifecycleState.DISPATCHING.value) is True
    assert can_transition(MessageLifecycleState.DISPATCHING.value, MessageLifecycleState.DELIVERED.value) is True
    assert can_transition(MessageLifecycleState.DISPATCHING.value, MessageLifecycleState.FAILED.value) is True
    assert can_transition(MessageLifecycleState.DISPATCHING.value, MessageLifecycleState.DLQ.value) is True


def test_invalid_transitions() -> None:
    assert can_transition(MessageLifecycleState.PENDING.value, MessageLifecycleState.DELIVERED.value) is False
    assert can_transition(MessageLifecycleState.DELIVERED.value, MessageLifecycleState.QUEUED.value) is False
    assert can_transition(MessageLifecycleState.DLQ.value, MessageLifecycleState.PENDING.value) is False


def test_set_message_state(db_state) -> None:
    msg = Message(
        message_type="notification",
        priority="normal",
        body_template="Hi",
        body_context={},
        recipient_id="u1",
        state=MessageLifecycleState.PENDING.value,
    )
    db_state.add(msg)
    db_state.flush()
    set_message_state(db_state, msg, MessageLifecycleState.QUEUED.value)
    assert msg.state == MessageLifecycleState.QUEUED.value


def test_set_message_state_invalid_raises(db_state) -> None:
    msg = Message(
        message_type="notification",
        priority="normal",
        body_template="Hi",
        body_context={},
        recipient_id="u1",
        state=MessageLifecycleState.PENDING.value,
    )
    db_state.add(msg)
    db_state.flush()
    with pytest.raises(ValueError, match="Invalid transition"):
        set_message_state(db_state, msg, MessageLifecycleState.DELIVERED.value)
