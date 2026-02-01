from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import SomJob
from app.services.audit import AuditService
from app.services.provenance import ProvenanceService


class JobService:
    def __init__(self, db: Session):
        self.db = db

    def create_and_enqueue(self, body: dict[str, Any], *, correlation_id: str | None) -> SomJob:
        job_type = body.get("type")
        parameters = body.get("parameters") or {}
        if job_type not in {"bulk_import_observations", "submit_preauth"}:
            raise ValueError("Unknown job type")
        if job_type == "bulk_import_observations":
            if not parameters.get("patientId"):
                raise ValueError("bulk_import_observations requires parameters.patientId")
            parameters.setdefault("count", 25)
        if job_type == "submit_preauth":
            if not parameters.get("preAuthId"):
                raise ValueError("submit_preauth requires parameters.preAuthId")

        if correlation_id:
            req = {"type": job_type, "parameters": parameters}
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="create",
                resource_type="Job",
                request_payload=req,
            )
            if prior and prior.get("jobId"):
                jid = uuid.UUID(prior["jobId"])
                job = self.db.get(SomJob, jid)
                if job:
                    return job

        job = SomJob(
            type=job_type,
            status="queued",
            progress=0,
            message="queued",
            error=None,
            parameters=parameters,
            outputs={},
            correlation_id=correlation_id,
            celery_task_id=None,
            created_time=dt.datetime.now(dt.timezone.utc),
            updated_time=dt.datetime.now(dt.timezone.utc),
            extensions={},
        )
        self.db.add(job)
        self.db.flush()
        prov = ProvenanceService(self.db).create(
            activity="create-job",
            author="system",
            correlation_id=correlation_id,
            target_resource_type="Job",
            target_resource_id=str(job.id),
            target_som_table="som_job",
            target_som_id=str(job.id),
        )

        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type="Job",
            resource_id=job.id,
            som_table="som_job",
            som_id=job.id,
            request_payload={"type": job_type, "parameters": parameters},
            result_payload={"jobId": str(job.id)},
        )

        # Commit so the worker (or eager task) can observe the SomJob row.
        self.db.commit()

        if job_type == "bulk_import_observations":
            from app.worker.tasks import bulk_import_observations

            task = bulk_import_observations.delay(str(job.id))
        else:
            from app.worker.tasks import submit_preauth

            task = submit_preauth.delay(str(job.id))

        # Avoid overwriting job status/progress updated by an eager task.
        self.db.execute(
            update(SomJob)
            .where(SomJob.id == job.id)
            .values(celery_task_id=task.id, updated_time=dt.datetime.now(dt.timezone.utc))
        )
        self.db.commit()
        job = self.db.get(SomJob, job.id) or job
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        job = self.db.get(SomJob, uuid.UUID(job_id))
        if not job:
            return None
        return self._to_dict(job)

    def list(self, *, status: str | None) -> dict[str, Any]:
        stmt = select(SomJob).order_by(SomJob.created_time.desc()).limit(200)
        if status:
            stmt = stmt.where(SomJob.status == status)
        jobs = self.db.execute(stmt).scalars().all()
        return {"jobs": [self._to_dict(j) for j in jobs]}

    @staticmethod
    def _to_dict(job: SomJob) -> dict[str, Any]:
        return {
            "id": str(job.id),
            "type": job.type,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "error": job.error,
            "parameters": job.parameters,
            "outputs": job.outputs,
            "correlationId": job.correlation_id,
            "createdTime": job.created_time.isoformat(),
            "updatedTime": job.updated_time.isoformat(),
        }
