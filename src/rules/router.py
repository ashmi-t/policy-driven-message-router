"""Takes rules output and filters by available contact info (email/phone)."""
from dataclasses import dataclass
from typing import List

from src.rules.engine import RulesEngine


@dataclass
class RoutingContext:
    user_id: str
    message_type: str
    priority: str
    recipient_email: str | None
    recipient_phone: str | None
    extra: dict | None = None


@dataclass
class RoutingDecision:
    channels: List[str]
    fallback_channels: List[str]
    max_retries: int


class Router:
    def __init__(self, rules_engine: RulesEngine) -> None:
        self.rules_engine = rules_engine

    def route(self, context: RoutingContext) -> RoutingDecision:
        primary, fallback, max_retries = self.rules_engine.decide_channels(
            user_id=context.user_id,
            message_type=context.message_type,
            priority=context.priority,
            context=context.extra,
        )
        channels = []
        if context.recipient_email and "email" in primary:
            channels.append("email")
        if context.recipient_phone and "sms" in primary:
            channels.append("sms")
        if not channels and primary:
            channels = [c for c in primary if (c == "email" and context.recipient_email) or (c == "sms" and context.recipient_phone)]
        fallback_filtered = []
        if context.recipient_email and "email" in fallback:
            fallback_filtered.append("email")
        if context.recipient_phone and "sms" in fallback:
            fallback_filtered.append("sms")
        return RoutingDecision(channels=channels, fallback_channels=fallback_filtered, max_retries=max_retries)
