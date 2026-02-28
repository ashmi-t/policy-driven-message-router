"""Routing engine: combines rules engine output and produces routing decision."""
from dataclasses import dataclass
from typing import List

from src.rules.engine import RulesEngine


@dataclass
class RoutingContext:
    """Context passed to the router."""

    user_id: str
    message_type: str
    priority: str
    recipient_email: str | None
    recipient_phone: str | None
    extra: dict | None = None


@dataclass
class RoutingDecision:
    """Result of routing: which channels to use and retry policy."""

    channels: List[str]  # Ordered list: try these first
    fallback_channels: List[str]
    max_retries: int


class Router:
    """Policy-based router: uses RulesEngine to decide channels and retry policy."""

    def __init__(self, rules_engine: RulesEngine) -> None:
        self.rules_engine = rules_engine

    def route(self, context: RoutingContext) -> RoutingDecision:
        """Decide how to deliver the message based on rules and preferences."""
        primary, fallback, max_retries = self.rules_engine.decide_channels(
            user_id=context.user_id,
            message_type=context.message_type,
            priority=context.priority,
            context=context.extra,
        )
        # Filter out channels we cannot use (e.g. no phone for SMS)
        channels = []
        if context.recipient_email and "email" in primary:
            channels.append("email")
        if context.recipient_phone and "sms" in primary:
            channels.append("sms")
        # If rules said something but we have no contact info, still record decision
        if not channels and primary:
            channels = [c for c in primary if (c == "email" and context.recipient_email) or (c == "sms" and context.recipient_phone)]
        fallback_filtered = []
        if context.recipient_email and "email" in fallback:
            fallback_filtered.append("email")
        if context.recipient_phone and "sms" in fallback:
            fallback_filtered.append("sms")
        return RoutingDecision(channels=channels, fallback_channels=fallback_filtered, max_retries=max_retries)
