"""User preferences API."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.orm_models import UserPreference
from src.models.schemas import UserPreferenceCreate

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.post("", response_model=dict)
def create_preference(
    body: UserPreferenceCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Create or update a user channel preference."""
    existing = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == body.user_id, UserPreference.channel == body.channel)
        .first()
    )
    if existing:
        existing.enabled = body.enabled
        existing.quiet_hours_start = body.quiet_hours_start
        existing.quiet_hours_end = body.quiet_hours_end
        existing.message_types_allowed = body.message_types_allowed
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "user_id": existing.user_id, "channel": existing.channel}
    pref = UserPreference(
        user_id=body.user_id,
        channel=body.channel,
        enabled=body.enabled,
        quiet_hours_start=body.quiet_hours_start,
        quiet_hours_end=body.quiet_hours_end,
        message_types_allowed=body.message_types_allowed,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return {"id": pref.id, "user_id": pref.user_id, "channel": pref.channel}


@router.get("/{user_id}", response_model=List[dict])
def list_preferences(user_id: str, db: Session = Depends(get_db)) -> List[dict]:
    """List preferences for a user."""
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).all()
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "channel": p.channel,
            "enabled": p.enabled,
            "quiet_hours_start": p.quiet_hours_start,
            "quiet_hours_end": p.quiet_hours_end,
            "message_types_allowed": p.message_types_allowed,
        }
        for p in prefs
    ]
