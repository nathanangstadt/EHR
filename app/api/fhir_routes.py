from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.mapping.fhir_dispatch import (
    fhir_create,
    fhir_read,
    fhir_search,
    fhir_update,
    fhir_history,
)


router = APIRouter()


@router.post("/{resource_type}")
def create_resource(
    resource_type: str,
    body: dict[str, Any],
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    if body.get("resourceType") and body.get("resourceType") != resource_type:
        raise HTTPException(status_code=400, detail="resourceType mismatch")
    try:
        return fhir_create(db, resource_type, body, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resource_type}/{id}")
def read_resource(resource_type: str, id: str, db: Session = Depends(get_db)):
    out = fhir_read(db, resource_type, id)
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.put("/{resource_type}/{id}")
def update_resource(
    resource_type: str,
    id: str,
    body: dict[str, Any],
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    if body.get("resourceType") and body.get("resourceType") != resource_type:
        raise HTTPException(status_code=400, detail="resourceType mismatch")
    try:
        out = fhir_update(db, resource_type, id, body, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("/{resource_type}")
def search_resource(
    resource_type: str,
    request: Request,
    _count: int = Query(default=50, ge=1, le=200),
    _sort: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    params: dict[str, Any] = {}
    for k, v in request.query_params.multi_items():
        if k in {"_count", "_sort"}:
            continue
        if k not in params:
            params[k] = v
        else:
            if isinstance(params[k], list):
                params[k].append(v)
            else:
                params[k] = [params[k], v]
    return fhir_search(db, resource_type, params=params, count=_count, sort=_sort)


@router.get("/Observation/{id}/_history")
def observation_history(id: str, db: Session = Depends(get_db)):
    return fhir_history(db, "Observation", id)
