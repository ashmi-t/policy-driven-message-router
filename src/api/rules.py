"""Routing rules CRUD endpoints."""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.orm_models import RoutingRule
from src.models.schemas import RoutingRuleCreate

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("", response_model=dict)
def create_rule(
    body: RoutingRuleCreate,
    db: Session = Depends(get_db),
) -> dict:
    rule = RoutingRule(
        name=body.name,
        priority_order=body.priority_order,
        active=body.active,
        conditions=body.conditions,
        channels=body.channels,
        fallback_channels=body.fallback_channels,
        max_retries=body.max_retries,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.get("", response_model=List[dict])
def list_rules(db: Session = Depends(get_db)) -> List[dict]:
    rules = db.query(RoutingRule).order_by(RoutingRule.priority_order, RoutingRule.id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "priority_order": r.priority_order,
            "active": r.active,
            "conditions": r.conditions,
            "channels": r.channels,
            "fallback_channels": r.fallback_channels,
            "max_retries": r.max_retries,
        }
        for r in rules
    ]


@router.get("/{rule_id}", response_model=dict)
def get_rule(rule_id: int, db: Session = Depends(get_db)) -> dict:
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {
        "id": rule.id,
        "name": rule.name,
        "priority_order": rule.priority_order,
        "active": rule.active,
        "conditions": rule.conditions,
        "channels": rule.channels,
        "fallback_channels": rule.fallback_channels,
        "max_retries": rule.max_retries,
    }


@router.patch("/{rule_id}", response_model=dict)
def update_rule(
    rule_id: int,
    body: RoutingRuleCreate,
    db: Session = Depends(get_db),
) -> dict:
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.name = body.name
    rule.priority_order = body.priority_order
    rule.active = body.active
    rule.conditions = body.conditions
    rule.channels = body.channels
    rule.fallback_channels = body.fallback_channels
    rule.max_retries = body.max_retries
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> None:
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
