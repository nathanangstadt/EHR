from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.payer.rules import PayerRuleService


router = APIRouter()


@router.get("/rules")
def get_active_rules(payer: str = Query(...), db: Session = Depends(get_db)):
    rs = PayerRuleService(db).get_active(payer=payer)
    if not rs:
        raise HTTPException(status_code=404, detail="No active rule set for payer")
    return PayerRuleService.to_dict(rs)


@router.put("/rules")
def put_active_rules(
    body: dict[str, Any],
    payer: str = Query(...),
    notes: str | None = Query(default=None),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    rules = body.get("rules") if "rules" in body else body
    if not isinstance(rules, dict):
        raise HTTPException(status_code=400, detail="rules must be an object")
    rs = PayerRuleService(db).upsert_active(payer=payer, rules=rules, notes=notes, correlation_id=x_correlation_id)
    return PayerRuleService.to_dict(rs)


@router.get("/rule-sets")
def list_rule_sets(payer: str | None = Query(default=None), db: Session = Depends(get_db)):
    rows = PayerRuleService(db).list(payer=payer)
    return {"ruleSets": [PayerRuleService.to_dict(r) for r in rows]}

