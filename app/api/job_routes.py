from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.jobs.service import JobService


router = APIRouter()


@router.post("")
def create_job(
    body: dict[str, Any],
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
):
    try:
        job = JobService(db).create_and_enqueue(body, correlation_id=x_correlation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"jobId": str(job.id)}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = JobService(db).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job


@router.get("")
def list_jobs(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    return JobService(db).list(status=status)
