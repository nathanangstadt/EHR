from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import Any

from app.worker.celery_app import celery_app
from sqlalchemy import select

from app.db.models import SomCondition, SomConcept, SomJob, SomPreAuthDecision, SomPreAuthRequest
from app.db.session import session_scope
from app.services.audit import AuditService
from app.services.payer.evaluator import evaluate_rules
from app.services.payer.rules import PayerRuleService
from app.services.provenance import ProvenanceService
from app.services.preauth.service import PreAuthService
from app.services.terminology import TerminologyService


def _update_job(job_id: uuid.UUID, **fields: Any) -> None:
    with session_scope() as db:
        job = db.get(SomJob, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_time = dt.datetime.now(dt.timezone.utc)


@celery_app.task(name="jobs.bulk_import_observations")
def bulk_import_observations(job_id: str) -> dict[str, Any]:
    jid = uuid.UUID(job_id)
    _update_job(jid, status="running", message="starting", progress=0)

    from app.db.models import SomObservation, SomObservationVersion, SomPatient

    created = 0
    with session_scope() as db:
        job = db.get(SomJob, jid)
        if not job:
            return {"ok": False}
        patient_id = job.parameters.get("patientId")
        count = int(job.parameters.get("count") or 25)
        if not patient_id:
            _update_job(jid, status="failed", error="Missing patientId", message="failed")
            return {"ok": False}
        patient = db.get(SomPatient, uuid.UUID(patient_id))
        if not patient:
            _update_job(jid, status="failed", error="Patient not found", message="failed")
            return {"ok": False}

        loinc = "http://loinc.org"
        hr = TerminologyService(db).normalize_concept(
            system=loinc, code="8867-4", display="Heart rate", version=None, correlation_id=job.correlation_id
        )
        prov = ProvenanceService(db).create(activity="bulk-import", author="worker", correlation_id=job.correlation_id)

        batch_size = 10
        start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=count)
        for i in range(0, count, batch_size):
            time.sleep(0.4)
            batch = min(batch_size, count - i)
            for j in range(batch):
                effective = start + dt.timedelta(minutes=i + j)
                o = SomObservation(
                    patient_id=patient.id,
                    encounter_id=None,
                    status="final",
                    category="vital",
                    code_concept_id=hr.id,
                    effective_time=effective,
                    value_type="quantity",
                    value_quantity_value=60 + ((i + j) % 30),
                    value_quantity_unit="bpm",
                    value_concept_id=None,
                    created_provenance_id=prov.id,
                    updated_provenance_id=None,
                    extensions={"source": "bulk-import"},
                )
                db.add(o)
                db.flush()
                db.add(
                    SomObservationVersion(
                        observation_id=o.id,
                        version=1,
                        recorded_time=dt.datetime.now(dt.timezone.utc),
                        status=o.status,
                        category=o.category,
                        code_concept_id=o.code_concept_id,
                        effective_time=o.effective_time,
                        value_type=o.value_type,
                        value_quantity_value=o.value_quantity_value,
                        value_quantity_unit=o.value_quantity_unit,
                        value_concept_id=None,
                        provenance_id=prov.id,
                        extensions=o.extensions,
                    )
                )
                created += 1

            _update_job(jid, progress=int(created * 100 / max(count, 1)), message=f"imported {created}/{count}")

        job.outputs = {"imported": created, "patientId": str(patient.id)}
        AuditService(db).emit(
            actor="worker",
            operation="create",
            correlation_id=job.correlation_id,
            resource_type="JobOutput",
            resource_id=job.id,
            som_table="som_job",
            som_id=job.id,
            request_payload=job.parameters,
            result_payload=job.outputs,
        )

    _update_job(jid, status="succeeded", progress=100, message="done")
    return {"ok": True, "imported": created}


@celery_app.task(name="jobs.submit_preauth")
def submit_preauth(job_id: str) -> dict[str, Any]:
    jid = uuid.UUID(job_id)
    _update_job(jid, status="running", message="assembling package", progress=10)
    time.sleep(0.5)

    with session_scope() as db:
        job = db.get(SomJob, jid)
        if not job:
            return {"ok": False}
        preauth_id = job.parameters.get("preAuthId")
        if not preauth_id:
            _update_job(jid, status="failed", error="Missing preAuthId", message="failed")
            return {"ok": False}
        pr = db.get(SomPreAuthRequest, uuid.UUID(preauth_id))
        if not pr:
            _update_job(jid, status="failed", error="PreAuth not found", message="failed")
            return {"ok": False}

        # Status: submitted -> in-review
        from_status = pr.status
        pr.status = "in-review"
        pr.version += 1
        PreAuthService(db)._status_change(pr.id, from_status=from_status, to_status="in-review", changed_by="payer-sim", correlation_id=job.correlation_id)
        AuditService(db).emit(
            actor="payer-sim",
            operation="update",
            correlation_id=job.correlation_id,
            resource_type="PreAuth",
            resource_id=pr.id,
            som_table="som_preauth_request",
            som_id=pr.id,
            request_payload={"from": from_status, "to": "in-review"},
            result_payload={"status": "in-review"},
        )

        _update_job(jid, message="payer reviewing", progress=40)
        time.sleep(1.0)

        diagnosis = db.get(SomCondition, pr.diagnosis_condition_id)
        diag_concept = diagnosis.code_concept if diagnosis else None
        sr_concept = pr.service_request.code_concept if pr.service_request else None

        diag_text = (diag_concept.display or "") if diag_concept else ""
        sr_text = (sr_concept.display or "") if sr_concept else ""
        sr_code = (sr_concept.code or "") if sr_concept else ""
        sr_system = sr_concept.code_system.system_uri if sr_concept else ""
        sr_priority = pr.service_request.priority if pr.service_request else None

        # Supporting documents attached to the preauth.
        from app.db.models import SomDocument, SomPreAuthSupportingDocument

        links = (
            db.execute(select(SomPreAuthSupportingDocument).where(SomPreAuthSupportingDocument.preauth_request_id == pr.id))
            .scalars()
            .all()
        )
        docs: list[dict[str, Any]] = []
        for link in links:
            doc = db.get(SomDocument, link.document_id)
            if not doc:
                continue
            docs.append(
                {
                    "id": str(doc.id),
                    "code": doc.type_concept.code,
                    "display": doc.type_concept.display,
                    "dateTime": (doc.date_time or doc.created_time).isoformat(),
                    "title": doc.title,
                    "role": link.role,
                }
            )

        now = dt.datetime.now(dt.timezone.utc)
        payer = pr.payer or "Acme Payer"
        ruleset = PayerRuleService(db).get_active(payer=payer)
        if not ruleset:
            # Fallback to a built-in default if no payer rule set exists.
            rules = {
                "schemaVersion": "1",
                "policies": [
                    {
                        "id": "mri-knee-oa",
                        "services": {
                            "codes": [
                                {"system": "http://www.ama-assn.org/go/cpt", "code": "73721"},
                                {"system": "http://www.ama-assn.org/go/cpt", "code": "73722"},
                                {"system": "http://www.ama-assn.org/go/cpt", "code": "73723"},
                            ]
                        },
                        "diagnosis": {"anyContains": ["osteoarthritis"]},
                        "requiredDocuments": [{"code": "knee-xray-report", "display": "Knee X-ray report (last 30 days)", "maxAgeDays": 30}],
                        "outcome": "approved",
                        "rationale": "Osteoarthritis criteria met with required documentation.",
                        "pendingInfoRationale": "Need recent knee X-ray report before approving advanced imaging.",
                    },
                    {
                        "id": "mri-knee-acute",
                        "services": {
                            "codes": [
                                {"system": "http://www.ama-assn.org/go/cpt", "code": "73721"},
                                {"system": "http://www.ama-assn.org/go/cpt", "code": "73722"},
                                {"system": "http://www.ama-assn.org/go/cpt", "code": "73723"},
                            ]
                        },
                        "diagnosis": {"anyContains": ["acute", "injury"]},
                        "requiredDocuments": [],
                        "outcome": "approved",
                        "rationale": "Acute injury criteria met for MRI knee.",
                    },
                ],
            }
        else:
            rules = ruleset.rules

        eval_out = evaluate_rules(
            rules=rules,
            now=now,
            service_system=sr_system or None,
            service_code=sr_code or None,
            service_text=sr_text or None,
            service_priority=sr_priority,
            diagnosis_system=diag_concept.code_system.system_uri if diag_concept else None,
            diagnosis_code=diag_concept.code if diag_concept else None,
            diagnosis_text=diag_text or None,
            preauth_priority=pr.priority,
            supporting_documents=docs,
        )

        outcome = eval_out["outcome"]
        reason_codes = eval_out["reasonCodes"]
        rationale = eval_out["rationale"]
        requested = eval_out.get("requestedAdditionalInfo") or []

        prov = ProvenanceService(db).create(activity="payer-determination", author="payer-sim", correlation_id=job.correlation_id)
        decision = SomPreAuthDecision(
            preauth_request_id=pr.id,
            decided_time=dt.datetime.now(dt.timezone.utc),
            outcome=outcome,
            reason_codes=reason_codes,
            rationale=rationale,
            requested_additional_info=requested,
            raw_payer_response={"outcome": outcome, "reasonCodes": reason_codes},
            provenance_id=prov.id,
            extensions={},
        )
        db.add(decision)
        db.flush()
        AuditService(db).emit(
            actor="payer-sim",
            operation="create",
            correlation_id=job.correlation_id,
            resource_type="PreAuthDecision",
            resource_id=decision.id,
            som_table="som_preauth_decision",
            som_id=decision.id,
            request_payload=None,
            result_payload={"preAuthId": str(pr.id), "outcome": outcome},
        )

        from_status2 = pr.status
        if outcome == "approved":
            pr.status = "approved"
        elif outcome == "denied":
            pr.status = "denied"
        else:
            pr.status = "pending-info"
        pr.version += 1
        PreAuthService(db)._status_change(pr.id, from_status=from_status2, to_status=pr.status, changed_by="payer-sim", correlation_id=job.correlation_id)
        AuditService(db).emit(
            actor="payer-sim",
            operation="update",
            correlation_id=job.correlation_id,
            resource_type="PreAuth",
            resource_id=pr.id,
            som_table="som_preauth_request",
            som_id=pr.id,
            request_payload={"from": from_status2, "to": pr.status},
            result_payload={"status": pr.status},
        )

        job.outputs = {"preAuthId": str(pr.id), "decisionId": str(decision.id), "outcome": outcome}

    _update_job(jid, status="succeeded", progress=100, message="done")
    return {"ok": True}
