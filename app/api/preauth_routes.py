from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.preauth.service import PreAuthService


router = APIRouter()


@router.post("")
def create_draft(
    body: dict[str, Any],
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        out = PreAuthService(db).create_draft(body, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out


@router.get("/{preauth_id}")
def get_preauth(preauth_id: str, db: Session = Depends(get_db)):
    out = PreAuthService(db).get(preauth_id)
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.post("/{preauth_id}/submit")
def submit_preauth(
    preauth_id: str,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        return PreAuthService(db).submit(preauth_id, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{preauth_id}/resubmit")
def resubmit_preauth(
    preauth_id: str,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        return PreAuthService(db).resubmit(preauth_id, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{preauth_id}/enqueue-review")
def enqueue_review(
    preauth_id: str,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        return PreAuthService(db).enqueue_review(preauth_id, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{preauth_id}/documents")
def attach_document(
    preauth_id: str,
    body: dict[str, Any],
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        return PreAuthService(db).attach_document(preauth_id, body, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{preauth_id}/status-history")
def status_history(preauth_id: str, db: Session = Depends(get_db)):
    return PreAuthService(db).status_history(preauth_id)


@router.get("/{preauth_id}/latest-decision")
def latest_decision(preauth_id: str, db: Session = Depends(get_db)):
    out = PreAuthService(db).latest_decision(preauth_id)
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("")
def search_preauth(
    patient: str | None = Query(default=None),
    status: str | None = Query(default=None),
    payer: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return PreAuthService(db).search(patient_id=patient, status=status, payer=payer)
