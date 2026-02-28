"""Tests for rules engine: rule matching and channel decision."""
import pytest
from sqlalchemy.orm import Session

from src.models.orm_models import RoutingRule
from src.rules.engine import RulesEngine, _rule_conditions_match


def test_conditions_match_message_type() -> None:
    assert _rule_conditions_match(
        {"message_types": ["critical_alert"]},
        {"message_type": "critical_alert"},
    ) is True
    assert _rule_conditions_match(
        {"message_types": ["critical_alert"]},
        {"message_type": "promotion"},
    ) is False
    assert _rule_conditions_match(
        {"message_types": []},
        {"message_type": "promotion"},
    ) is True  # empty = no filter


def test_conditions_match_priority() -> None:
    assert _rule_conditions_match(
        {"priorities": ["critical", "high"]},
        {"priority": "critical"},
    ) is True
    assert _rule_conditions_match(
        {"priorities": ["critical"]},
        {"priority": "low"},
    ) is False


@pytest.fixture
def db_with_rules(db: Session) -> Session:
    db.add(
        RoutingRule(
            name="Critical",
            priority_order=0,
            active=True,
            conditions={"message_types": ["critical_alert"], "priorities": ["critical"]},
            channels=["sms", "email"],
            fallback_channels=["email"],
            max_retries=5,
        )
    )
    db.add(
        RoutingRule(
            name="Promo",
            priority_order=10,
            active=True,
            conditions={"message_types": ["promotion"]},
            channels=["email"],
            fallback_channels=[],
            max_retries=2,
        )
    )
    db.add(
        RoutingRule(
            name="Default",
            priority_order=100,
            active=True,
            conditions={},
            channels=["email"],
            fallback_channels=["sms"],
            max_retries=3,
        )
    )
    db.commit()
    return db


def test_matching_rule_critical(db_with_rules: Session) -> None:
    engine = RulesEngine(db_with_rules)
    rule = engine.get_matching_rule("critical_alert", "critical")
    assert rule is not None
    assert rule.name == "Critical"
    assert set(rule.channels) == {"sms", "email"}


def test_matching_rule_promotion(db_with_rules: Session) -> None:
    engine = RulesEngine(db_with_rules)
    rule = engine.get_matching_rule("promotion", "normal")
    assert rule is not None
    assert rule.name == "Promo"
    assert rule.channels == ["email"]


def test_matching_rule_default(db_with_rules: Session) -> None:
    engine = RulesEngine(db_with_rules)
    rule = engine.get_matching_rule("notification", "low")
    assert rule is not None
    assert rule.name == "Default"


def test_decide_channels_returns_fallback(db_with_rules: Session) -> None:
    engine = RulesEngine(db_with_rules)
    channels, fallback, max_retries = engine.decide_channels("user1", "critical_alert", "critical")
    assert "sms" in channels and "email" in channels
    assert "email" in fallback
    assert max_retries == 5
