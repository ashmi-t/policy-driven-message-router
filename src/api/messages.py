"""Message submit and query APIs."""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.orm_models import Message, MessageLifecycleState
from src.models.schemas import MessageCreate, MessageStatusResponse
from src.state import set_message_state
from src.tasks import dispatch_message

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=dict)
def submit_message(
    body: MessageCreate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Submit a message for routing. Message is queued and dispatched asynchronously.
    At least one of recipient_email or recipient_phone is required so the router has a channel to use.
    """
    if not body.recipient_email and not body.recipient_phone:
        raise HTTPException(
            status_code=400,
            detail="At least one of recipient_email or recipient_phone is required for delivery.",
        )
    msg = Message(
        message_type=body.message_type.value,
        priority=body.priority.value,
        subject=body.subject,
        body_template=body.body_template,
        body_context=body.body_context,
        recipient_id=body.recipient_id,
        recipient_email=body.recipient_email,
        recipient_phone=body.recipient_phone,
        metadata_=getattr(body, "metadata", None) or (body.model_dump().get("metadata") or {}),
        state=MessageLifecycleState.PENDING.value,
    )
    db.add(msg)
    db.flush()
    set_message_state(db, msg, MessageLifecycleState.QUEUED.value)
    db.commit()
    db.refresh(msg)
    dispatch_message.apply_async(args=[msg.id])
    return {"id": msg.external_id, "status": "queued", "message_id": msg.id}


@router.get("/{external_id}", response_model=MessageStatusResponse)
def get_message_status(
    external_id: str,
    db: Session = Depends(get_db),
) -> MessageStatusResponse:
    """Get message status and delivery state by external ID."""
    msg = db.query(Message).filter(Message.external_id == external_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    deliveries = [
        {
            "id": d.id,
            "channel": d.channel,
            "state": d.state,
            "retry_count": d.retry_count,
            "provider_id": d.provider_id,
            "last_error": d.last_error,
        }
        for d in msg.deliveries
    ]
    failure_reason = (msg.metadata_ or {}).get("failure_reason") if msg.metadata_ else None
    return MessageStatusResponse(
        id=msg.external_id,
        external_id=msg.external_id,
        state=msg.state,
        message_type=msg.message_type,
        priority=msg.priority,
        created_at=msg.created_at,
        deliveries=deliveries,
        failure_reason=failure_reason,
    )


@router.get("", response_model=List[MessageStatusResponse])
def list_messages(
    limit: int = 50,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> List[MessageStatusResponse]:
    """List messages with optional state filter."""
    q = db.query(Message).order_by(Message.created_at.desc()).limit(limit)
    if state:
        q = q.filter(Message.state == state)
    messages = q.all()
    return [
        MessageStatusResponse(
            id=m.external_id,
            external_id=m.external_id,
            state=m.state,
            message_type=m.message_type,
            priority=m.priority,
            created_at=m.created_at,
            deliveries=[
                {
                    "id": d.id,
                    "channel": d.channel,
                    "state": d.state,
                    "retry_count": d.retry_count,
                    "provider_id": d.provider_id,
                    "last_error": d.last_error,
                }
                for d in m.deliveries
            ],
            failure_reason=(m.metadata_ or {}).get("failure_reason") if m.metadata_ else None,
        )
        for m in messages
    ]
