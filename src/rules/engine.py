"""Matches messages to rules and filters channels by user preferences."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.models.orm_models import MessageType, Priority, RoutingRule, UserPreference


def _parse_time(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    try:
        parts = s.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def _current_minutes() -> int:
    now = datetime.utcnow()
    return now.hour * 60 + now.minute


def _in_quiet_hours(start: Optional[str], end: Optional[str]) -> bool:
    """Handles wraparound (e.g. 22:00–08:00 means overnight)."""
    s, e = _parse_time(start), _parse_time(end)
    if s is None and e is None:
        return False
    now = _current_minutes()
    if s is not None and e is not None:
        if s <= e:
            return s <= now < e
        return now >= s or now < e
    if s is not None:
        return now >= s
    if e is not None:
        return now < e
    return False


def _rule_conditions_match(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
    message_type = context.get("message_type")
    if message_type and "message_types" in conditions:
        allowed = conditions["message_types"]
        if allowed and message_type not in allowed:
            return False

    priority = context.get("priority")
    if priority and "priorities" in conditions:
        allowed = conditions["priorities"]
        if allowed and priority not in allowed:
            return False

    if "time_window_start" in conditions or "time_window_end" in conditions:
        now_m = _current_minutes()
        start = _parse_time(conditions.get("time_window_start"))
        end = _parse_time(conditions.get("time_window_end"))
        if start is not None and now_m < start:
            return False
        if end is not None and now_m >= end:
            return False

    return True


def _filter_by_user_preferences(
    db: Session,
    user_id: str,
    channels: List[str],
    message_type: str,
) -> List[str]:
    prefs = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == user_id, UserPreference.enabled == True)
        .all()
    )
    if not prefs:
        return channels

    allowed = []
    for p in prefs:
        if p.channel not in channels:
            continue
        if _in_quiet_hours(p.quiet_hours_start, p.quiet_hours_end):
            continue
        if p.message_types_allowed and message_type not in p.message_types_allowed:
            continue
        allowed.append(p.channel)

    if prefs and not allowed:
        return []
    return allowed if allowed else channels


class RulesEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_matching_rule(
        self,
        message_type: str,
        priority: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[RoutingRule]:
        context = context or {}
        context.setdefault("message_type", message_type)
        context.setdefault("priority", priority)

        rules = (
            self.db.query(RoutingRule)
            .filter(RoutingRule.active == True)
            .order_by(RoutingRule.priority_order, RoutingRule.id)
            .all()
        )
        for rule in rules:
            if _rule_conditions_match(rule.conditions, context):
                return rule
        return None

    def decide_channels(
        self,
        user_id: str,
        message_type: str,
        priority: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[str], List[str], int]:
        rule = self.get_matching_rule(message_type, priority, context)
        if not rule:
            return [], [], 3

        channels = list(rule.channels) if rule.channels else []
        fallback = list(rule.fallback_channels) if rule.fallback_channels else []
        max_retries = rule.max_retries if rule.max_retries is not None else 3

        filtered = _filter_by_user_preferences(self.db, user_id, channels, message_type)
        return filtered, fallback, max_retries
