"""Seeds default rules on first run. Called from main lifespan; can also run manually."""
import sys

from src.db import SessionLocal
from src.models.orm_models import RoutingRule


DEFAULT_RULES = [
    {
        "name": "Critical alerts: SMS + Email",
        "priority_order": 0,
        "conditions": {"message_types": ["critical_alert"], "priorities": ["critical", "high"]},
        "channels": ["sms", "email"],
        "fallback_channels": ["email"],
        "max_retries": 5,
    },
    {
        "name": "Promotions: Email only",
        "priority_order": 10,
        "conditions": {"message_types": ["promotion"]},
        "channels": ["email"],
        "fallback_channels": [],
        "max_retries": 2,
    },
    {
        "name": "Transactional: Email",
        "priority_order": 20,
        "conditions": {"message_types": ["transactional"]},
        "channels": ["email"],
        "fallback_channels": ["sms"],
        "max_retries": 3,
    },
    {
        "name": "Default: Email, fallback SMS",
        "priority_order": 100,
        "conditions": {},
        "channels": ["email"],
        "fallback_channels": ["sms"],
        "max_retries": 3,
    },
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(RoutingRule).count()
        if existing > 0:
            print("Rules already exist, skipping seed.")
            return
        for r in DEFAULT_RULES:
            rule = RoutingRule(
                name=r["name"],
                priority_order=r["priority_order"],
                active=True,
                conditions=r["conditions"],
                channels=r["channels"],
                fallback_channels=r["fallback_channels"],
                max_retries=r["max_retries"],
            )
            db.add(rule)
        db.commit()
        print("Seeded", len(DEFAULT_RULES), "rules.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    sys.exit(0)
