"""SQLAlchemy ORM models and message lifecycle state."""
from datetime import datetime
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class MessageLifecycleState(str, PyEnum):
    """State machine for message lifecycle."""

    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    DELIVERED = "delivered"
    FAILED = "failed"
    DLQ = "dlq"


class MessageType(str, PyEnum):
    """Supported message types for routing rules."""

    CRITICAL_ALERT = "critical_alert"
    PROMOTION = "promotion"
    TRANSACTIONAL = "transactional"
    NOTIFICATION = "notification"


class Priority(str, PyEnum):
    """Message priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ChannelType(str, PyEnum):
    """Delivery channel identifiers."""

    EMAIL = "email"
    SMS = "sms"


def generate_uuid():
    return str(uuid4())


class Message(Base):
    """Incoming message to be routed and delivered."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(36), unique=True, default=generate_uuid)
    message_type = Column(String(32), nullable=False)
    priority = Column(String(16), nullable=False)
    subject = Column(String(512))
    body_template = Column(String(128), nullable=False)
    body_context = Column(JSON, default=dict)
    recipient_id = Column(String(128), nullable=False)
    recipient_email = Column(String(256))
    recipient_phone = Column(String(32))
    state = Column(String(32), default=MessageLifecycleState.PENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_ = Column("metadata", JSON, default=dict)

    deliveries = relationship("MessageDelivery", back_populates="message", cascade="all, delete-orphan")


class MessageDelivery(Base):
    """Per-channel delivery attempt (one message can have multiple deliveries)."""

    __tablename__ = "message_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    channel = Column(String(32), nullable=False)  # ChannelType value
    state = Column(String(32), default=MessageLifecycleState.PENDING.value)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_error = Column(Text)
    provider_id = Column(String(256))  # External ID from Mailjet/Twilio
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    message = relationship("Message", back_populates="deliveries")


class RoutingRule(Base):
    """Rule for routing: conditions + channels + retry policy."""

    __tablename__ = "routing_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    priority_order = Column(Integer, default=0)  # Lower = evaluated first
    active = Column(Boolean, default=True)
    # Conditions (JSON): message_types[], priorities[], time_windows, etc.
    conditions = Column(JSON, nullable=False)
    # Channels to use: ["email"], ["sms"], ["email", "sms"]
    channels = Column(JSON, nullable=False)  # list of channel names
    # Fallback: if primary channel fails, try these
    fallback_channels = Column(JSON, default=list)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserPreference(Base):
    """User preferences for channel and time (used by routing)."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    enabled = Column(Boolean, default=True)
    # Optional: quiet hours or allowed time windows
    quiet_hours_start = Column(String(5))  # "22:00"
    quiet_hours_end = Column(String(5))    # "08:00"
    message_types_allowed = Column(JSON, default=list)  # empty = all
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
