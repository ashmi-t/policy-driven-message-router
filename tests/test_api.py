"""Tests for message and rules API."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.orm_models import RoutingRule


@pytest.fixture
def seeded_rules(db: Session) -> None:
    db.add(
        RoutingRule(
            name="Email only",
            priority_order=0,
            active=True,
            conditions={"message_types": ["promotion"]},
            channels=["email"],
            fallback_channels=[],
            max_retries=2,
        )
    )
    db.commit()


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@patch("src.api.messages.dispatch_message")
def test_submit_message(mock_dispatch, client: TestClient, seeded_rules: None) -> None:
    r = client.post(
        "/messages",
        json={
            "message_type": "promotion",
            "priority": "normal",
            "body_template": "Hello {{ name }}",
            "body_context": {"name": "User"},
            "recipient_id": "user1",
            "recipient_email": "user@example.com",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["status"] == "queued"
    mock_dispatch.apply_async.assert_called_once()


@patch("src.api.messages.dispatch_message")
def test_get_message_status(mock_dispatch, client: TestClient, seeded_rules: None) -> None:
    post_r = client.post(
        "/messages",
        json={
            "message_type": "promotion",
            "priority": "normal",
            "body_template": "Hi",
            "body_context": {},
            "recipient_id": "user1",
            "recipient_email": "user@example.com",
        },
    )
    external_id = post_r.json()["id"]
    r = client.get(f"/messages/{external_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["external_id"] == external_id
    assert data["state"] in ("queued", "dispatching", "delivered", "failed", "dlq")
    assert "deliveries" in data


def test_get_message_not_found(client: TestClient) -> None:
    r = client.get("/messages/nonexistent-id")
    assert r.status_code == 404


def test_create_rule(client: TestClient) -> None:
    r = client.post(
        "/rules",
        json={
            "name": "Test rule",
            "priority_order": 5,
            "conditions": {"message_types": ["transactional"]},
            "channels": ["email"],
            "fallback_channels": ["sms"],
            "max_retries": 3,
        },
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Test rule"


def test_list_rules(client: TestClient, seeded_rules: None) -> None:
    r = client.get("/rules")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_create_preference(client: TestClient) -> None:
    r = client.post(
        "/preferences",
        json={
            "user_id": "user1",
            "channel": "email",
            "enabled": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["channel"] == "email"
