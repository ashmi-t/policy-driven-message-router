"""SQLAlchemy ORM models."""
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
    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    DELIVERED = "delivered"
    FAILED = "failed"
    DLQ = "dlq"


class MessageType(str, PyEnum):
    CRITICAL_ALERT = "critical_alert"
    PROMOTION = "promotion"
    TRANSACTIONAL = "transactional"
    NOTIFICATION = "notification"


class Priority(str, PyEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ChannelType(str, PyEnum):
    EMAIL = "email"
    SMS = "sms"


def generate_uuid():
    return str(uuid4())


class Message(Base):
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
    """One delivery attempt per channel. A message can have multiple deliveries (e.g. SMS + email)."""

    __tablename__ = "message_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    channel = Column(String(32), nullable=False)
    state = Column(String(32), default=MessageLifecycleState.PENDING.value)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_error = Column(Text)
    provider_id = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    message = relationship("Message", back_populates="deliveries")


class RoutingRule(Base):
    """Maps conditions (message type, priority, time) to channels and retry policy."""

    __tablename__ = "routing_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    priority_order = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    conditions = Column(JSON, nullable=False)
    channels = Column(JSON, nullable=False)
    fallback_channels = Column(JSON, default=list)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserPreference(Base):
    """Per-user, per-channel: enabled, quiet hours, allowed message types."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    enabled = Column(Boolean, default=True)
    quiet_hours_start = Column(String(5))
    quiet_hours_end = Column(String(5))
    message_types_allowed = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
