from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.audit import AuditService
from app.services.admin.service import AdminService
from app.services.internal import InternalService
from app.services.scenarios.service import ScenarioService


router = APIRouter()


@router.get("/mapping-trace")
def mapping_trace(
    correlation_id: str | None = Query(default=None, alias="correlationId"),
    resource_type: str | None = Query(default=None, alias="resourceType"),
    resource_id: str | None = Query(default=None, alias="resourceId"),
    db: Session = Depends(get_db),
):
    return AuditService(db).trace(correlation_id=correlation_id, resource_type=resource_type, resource_id=resource_id)


@router.get("/som/{resource_type}/{id}")
def som_backing(resource_type: str, id: str, db: Session = Depends(get_db)):
    out = InternalService(db).som_backing(resource_type, id)
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("/observation/{id}/versions")
def observation_versions(id: str, db: Session = Depends(get_db)):
    out = InternalService(db).observation_versions(id)
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.post("/admin/reset")
def reset_seed_data(
    body: dict | None = None,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    body = body or {}
    try:
        return AdminService(db).reset_seed_data(correlation_id=x_correlation_id, seed_data=bool(body.get("seed", True)))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scenarios/templates")
def list_scenario_templates(db: Session = Depends(get_db)):
    return ScenarioService(db).list_templates()


@router.post("/scenarios")
def create_scenario(
    body: dict,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        return ScenarioService(db).create_from_template(body, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
