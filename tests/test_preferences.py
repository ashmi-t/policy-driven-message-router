"""Tests for preference filtering in routing."""
import pytest
from sqlalchemy.orm import Session

from src.models.orm_models import UserPreference, RoutingRule
from src.rules.engine import RulesEngine


@pytest.fixture
def rules(db: Session) -> None:
    """Seed one rule: email + sms."""
    db.add(
        RoutingRule(
            name="test",
            priority_order=0,
            active=True,
            conditions={"message_types": ["notification"]},
            channels=["email", "sms"],
            fallback_channels=[],
            max_retries=2,
        )
    )
    db.commit()


def test_no_preferences_returns_all_channels(db: Session, rules: None) -> None:
    """When user has no preferences, all rule channels are returned."""
    engine = RulesEngine(db)
    channels, fallback, max_retries = engine.decide_channels(
        user_id="user1",
        message_type="notification",
        priority="normal",
    )
    assert set(channels) == {"email", "sms"}
    assert max_retries == 2


def test_preference_disables_channel(db: Session, rules: None) -> None:
    """User disables SMS -> only email returned."""
    db.add(
        UserPreference(user_id="user1", channel="email", enabled=True)
    )
    db.add(
        UserPreference(user_id="user1", channel="sms", enabled=False)
    )
    db.commit()
    engine = RulesEngine(db)
    channels, _, _ = engine.decide_channels(
        user_id="user1",
        message_type="notification",
        priority="normal",
    )
    assert channels == ["email"]


def test_preference_message_type_filter(db: Session, rules: None) -> None:
    """User allows only promotion on email; notification not allowed -> email excluded for notification."""
    db.add(
        UserPreference(
            user_id="user1",
            channel="email",
            enabled=True,
            message_types_allowed=["promotion"],
        )
    )
    db.add(
        UserPreference(
            user_id="user1",
            channel="sms",
            enabled=True,
        )
    )
    db.commit()
    engine = RulesEngine(db)
    channels, _, _ = engine.decide_channels(
        user_id="user1",
        message_type="notification",
        priority="normal",
    )
    # Email not in allowed message_types for user; sms has no restriction
    assert "email" not in channels
    assert "sms" in channels


def test_quiet_hours_excluded(db: Session, rules: None) -> None:
    """If we mock or test quiet hours, channel can be excluded. (Simplified: we only check _in_quiet_hours logic.)"""
    from src.rules.engine import _in_quiet_hours, _parse_time, _current_minutes
    # 22:00 - 08:00: at 23:00 we're in quiet hours
    assert _parse_time("22:00") == 22 * 60
    assert _parse_time("08:00") == 8 * 60
    # Just ensure the helper behaves: 23:00 is after 22:00 and before 08:00 (next day)
    # _in_quiet_hours("22:00", "08:00") at 23*60: 23*60 >= 22*60 -> True
    # So we're in quiet hours. User pref with quiet hours would exclude that channel in decide_channels.
    assert _in_quiet_hours("22:00", "08:00") == (_current_minutes() >= 22 * 60 or _current_minutes() < 8 * 60)
