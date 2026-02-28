"""Request/response schemas for API validation."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageType(str, Enum):
    CRITICAL_ALERT = "critical_alert"
    PROMOTION = "promotion"
    TRANSACTIONAL = "transactional"
    NOTIFICATION = "notification"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessageCreate(BaseModel):
    message_type: MessageType
    priority: Priority = Priority.NORMAL
    subject: Optional[str] = None
    body_template: str = Field(..., min_length=1)
    body_context: Dict[str, Any] = Field(default_factory=dict)
    recipient_id: str
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata")


class MessageStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_id: str
    state: str
    message_type: str
    priority: str
    created_at: datetime
    deliveries: List[Dict[str, Any]] = Field(default_factory=list)
    failure_reason: Optional[str] = None


class RoutingRuleCreate(BaseModel):
    name: str
    priority_order: int = 0
    active: bool = True
    conditions: Dict[str, Any]
    channels: List[str]
    fallback_channels: List[str] = Field(default_factory=list)
    max_retries: int = 3


class UserPreferenceCreate(BaseModel):
    user_id: str
    channel: str
    enabled: bool = True
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    message_types_allowed: List[str] = Field(default_factory=list)
