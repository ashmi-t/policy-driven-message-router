"""Message lifecycle state machine and transitions."""
from src.models.orm_models import Message, MessageDelivery, MessageLifecycleState
from sqlalchemy.orm import Session

# Valid transitions for message state
TRANSITIONS = {
    MessageLifecycleState.PENDING: [MessageLifecycleState.QUEUED],
    MessageLifecycleState.QUEUED: [MessageLifecycleState.DISPATCHING],
    MessageLifecycleState.DISPATCHING: [
        MessageLifecycleState.DELIVERED,
        MessageLifecycleState.FAILED,
        MessageLifecycleState.DLQ,
    ],
    MessageLifecycleState.DELIVERED: [],
    MessageLifecycleState.FAILED: [MessageLifecycleState.QUEUED],  # retry
    MessageLifecycleState.DLQ: [],
}


def can_transition(current: str, next_state: str) -> bool:
    next_enum = MessageLifecycleState(next_state) if isinstance(next_state, str) else next_state
    try:
        current_enum = MessageLifecycleState(current) if isinstance(current, str) else current
    except ValueError:
        return False
    return next_enum in TRANSITIONS.get(current_enum, [])


def set_message_state(db: Session, message: Message, new_state: str) -> None:
    if not can_transition(message.state, new_state):
        raise ValueError(f"Invalid transition from {message.state} to {new_state}")
    message.state = new_state
    db.flush()


def set_delivery_state(db: Session, delivery: MessageDelivery, new_state: str) -> None:
    if not can_transition(delivery.state, new_state):
        raise ValueError(f"Invalid delivery transition from {delivery.state} to {new_state}")
    delivery.state = new_state
    db.flush()
