from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    SomCondition,
    SomDocument,
    SomEncounter,
    SomJob,
    SomObservation,
    SomPreAuthDecision,
    SomPreAuthPackageSnapshot,
    SomPreAuthRequest,
    SomPreAuthSupportingDocument,
    SomPreAuthStatusHistory,
    SomPractitioner,
    SomServiceRequest,
)
from app.services.audit import AuditService
from app.services.jobs.service import JobService
from app.services.provenance import ProvenanceService


class PreAuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_draft(self, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        if correlation_id:
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="create",
                resource_type="PreAuth",
                request_payload=body,
            )
            if prior:
                return prior

        patient_id = _uuid(body.get("patientId"))
        practitioner_id = _uuid(body.get("practitionerId"))
        diagnosis_id = _uuid(body.get("diagnosisConditionId"))
        sr_id = _uuid(body.get("serviceRequestId"))
        encounter_id = _uuid(body.get("encounterId")) if body.get("encounterId") else None
        organization_id = _uuid(body.get("organizationId")) if body.get("organizationId") else None

        if not self.db.get(SomPractitioner, practitioner_id):
            raise ValueError("Practitioner not found")
        if not self.db.get(SomCondition, diagnosis_id):
            raise ValueError("Diagnosis Condition not found")
        if not self.db.get(SomServiceRequest, sr_id):
            raise ValueError("ServiceRequest not found")
        if encounter_id and not self.db.get(SomEncounter, encounter_id):
            raise ValueError("Encounter not found")

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        pr = SomPreAuthRequest(
            patient_id=patient_id,
            encounter_id=encounter_id,
            practitioner_id=practitioner_id,
            organization_id=organization_id,
            diagnosis_condition_id=diagnosis_id,
            service_request_id=sr_id,
            status="draft",
            priority=body.get("priority") or "routine",
            payer=body.get("payer"),
            policy_id=body.get("policyId"),
            notes=body.get("notes"),
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={"supportingObservationIds": body.get("supportingObservationIds") or []},
        )
        self.db.add(pr)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type="PreAuth",
            target_resource_id=str(pr.id),
            target_som_table="som_preauth_request",
            target_som_id=str(pr.id),
        )

        self._status_change(
            pr.id,
            from_status=None,
            to_status="draft",
            changed_by="system",
            correlation_id=correlation_id,
            provenance_id=prov.id,
        )

        out = self.get(str(pr.id)) or {"id": str(pr.id)}
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type="PreAuth",
            resource_id=pr.id,
            som_table="som_preauth_request",
            som_id=pr.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def submit(self, preauth_id: str, *, correlation_id: str | None) -> dict[str, Any]:
        # Draft -> submitted
        return self._submit_like(preauth_id, correlation_id=correlation_id, mode="submit")

    def resubmit(self, preauth_id: str, *, correlation_id: str | None) -> dict[str, Any]:
        # Pending-info -> resubmitted (requires requested docs satisfied)
        return self._submit_like(preauth_id, correlation_id=correlation_id, mode="resubmit")

    def enqueue_review(self, preauth_id: str, *, correlation_id: str | None) -> dict[str, Any]:
        """
        Recovery endpoint: if a PreAuth is in-flight (submitted/resubmitted/in-review) but no job is running
        (e.g. due to a prior idempotency collision), enqueue a submit_preauth job without re-snapshotting.
        """
        req = {"preAuthId": preauth_id}
        if correlation_id:
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="enqueue-review",
                resource_type="PreAuth",
                request_payload=req,
            )
            if prior:
                return prior

        pr = self.db.get(SomPreAuthRequest, uuid.UUID(preauth_id))
        if not pr:
            raise ValueError("PreAuthRequest not found")
        if pr.status not in {"submitted", "resubmitted", "in-review"}:
            raise ValueError(f"Cannot enqueue review from status {pr.status}")

        # If there's already a decision, there's nothing to re-enqueue.
        latest = self.latest_decision(preauth_id)
        if latest:
            raise ValueError("Cannot enqueue review: decision already exists")

        existing = (
            self.db.execute(
                select(SomJob)
                .where(SomJob.type == "submit_preauth")
                .where(SomJob.parameters["preAuthId"].as_string() == str(pr.id))
                .where(SomJob.status.in_(["queued", "running"]))
                .order_by(desc(SomJob.created_time))
                .limit(1)
            )
            .scalar_one_or_none()
        )

        if existing:
            out = {"preAuthId": str(pr.id), "jobId": str(existing.id), "existing": True}
        else:
            job = JobService(self.db).create_and_enqueue(
                {"type": "submit_preauth", "parameters": {"preAuthId": str(pr.id)}},
                correlation_id=correlation_id,
            )
            out = {"preAuthId": str(pr.id), "jobId": str(job.id), "existing": False}

        AuditService(self.db).emit(
            actor="system",
            operation="enqueue-review",
            correlation_id=correlation_id,
            resource_type="PreAuth",
            resource_id=pr.id,
            som_table="som_preauth_request",
            som_id=pr.id,
            request_payload=req,
            result_payload=out,
        )
        return out

    def _submit_like(self, preauth_id: str, *, correlation_id: str | None, mode: str) -> dict[str, Any]:
        op = "submit" if mode == "submit" else "resubmit"
        req = {"preAuthId": preauth_id, "mode": mode}
        if correlation_id:
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation=op,
                resource_type="PreAuth",
                request_payload=req,
            )
            if prior:
                return prior

        pr = self.db.get(SomPreAuthRequest, uuid.UUID(preauth_id))
        if not pr:
            raise ValueError("PreAuthRequest not found")
        if mode == "submit":
            if pr.status != "draft":
                raise ValueError(f"Cannot submit from status {pr.status} (use /resubmit for pending-info)")
            new_status = "submitted"
            activity = "submit"
        else:
            if pr.status != "pending-info":
                raise ValueError(f"Cannot resubmit from status {pr.status}")
            self._validate_pending_info_requirements(pr)
            new_status = "resubmitted"
            activity = "resubmit"

        if not pr.patient_id or not pr.practitioner_id or not pr.diagnosis_condition_id or not pr.service_request_id:
            raise ValueError("PreAuthRequest missing required links")

        from_status = pr.status
        pr.status = new_status
        pr.version += 1
        prov = ProvenanceService(self.db).create(
            activity=activity,
            author=None,
            correlation_id=correlation_id,
            target_resource_type="PreAuth",
            target_resource_id=str(pr.id),
            target_som_table="som_preauth_request",
            target_som_id=str(pr.id),
        )
        pr.updated_provenance_id = prov.id

        self._status_change(
            pr.id,
            from_status=from_status,
            to_status=new_status,
            changed_by="system",
            correlation_id=correlation_id,
            provenance_id=prov.id,
        )

        # Snapshot should reflect the status being sent to payer (submitted/resubmitted), and include any
        # documents already attached at the time of this submission.
        snapshot = self._create_snapshot(pr, correlation_id=correlation_id)

        job = JobService(self.db).create_and_enqueue(
            {"type": "submit_preauth", "parameters": {"preAuthId": str(pr.id), "snapshotId": str(snapshot.id), "mode": mode}},
            correlation_id=correlation_id,
        )

        out = {"preAuthId": str(pr.id), "snapshotId": str(snapshot.id), "jobId": str(job.id), "mode": mode}
        AuditService(self.db).emit(
            actor="system",
            operation=op,
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type="PreAuth",
            resource_id=pr.id,
            som_table="som_preauth_request",
            som_id=pr.id,
            request_payload=req,
            result_payload=out,
        )
        return out

    def _validate_pending_info_requirements(self, pr: SomPreAuthRequest) -> None:
        latest = (
            self.db.execute(
                select(SomPreAuthDecision)
                .where(SomPreAuthDecision.preauth_request_id == pr.id)
                .order_by(desc(SomPreAuthDecision.decided_time))
                .limit(1)
            )
            .scalar_one_or_none()
        )
        if not latest or latest.outcome != "pending-info":
            raise ValueError("Cannot resubmit: no pending-info decision found")
        reqs = latest.requested_additional_info or []
        missing_codes: list[str] = []

        doc_links = (
            self.db.execute(
                select(SomPreAuthSupportingDocument)
                .where(SomPreAuthSupportingDocument.preauth_request_id == pr.id)
                .order_by(SomPreAuthSupportingDocument.added_time.desc())
            )
            .scalars()
            .all()
        )
        docs: list[SomDocument] = []
        for link in doc_links:
            d = self.db.get(SomDocument, link.document_id)
            if d:
                docs.append(d)

        now = dt.datetime.now(dt.timezone.utc)
        for r in reqs:
            if (r.get("type") or "").lower() != "document":
                continue
            code = str(r.get("code") or "")
            max_age = int(r.get("maxAgeDays") or 30)
            ok = False
            for d in docs:
                if (d.type_concept.code or "").lower() != code.lower():
                    continue
                t = d.date_time or d.created_time
                if now - t <= dt.timedelta(days=max_age):
                    ok = True
                    break
            if not ok:
                missing_codes.append(code)

        if missing_codes:
            raise ValueError(f"Missing required documents for resubmission: {', '.join(sorted(set(missing_codes)))}")

    def attach_document(self, preauth_id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        doc_id = body.get("documentId")
        if not doc_id:
            raise ValueError("documentId required")
        role = body.get("role") or "supporting"
        req = {"preAuthId": preauth_id, "documentId": str(doc_id), "role": role}

        if correlation_id:
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="create",
                resource_type="PreAuthSupportingDocument",
                request_payload=req,
            )
            if prior:
                return prior

        pr = self.db.get(SomPreAuthRequest, uuid.UUID(preauth_id))
        if not pr:
            raise ValueError("PreAuthRequest not found")
        doc = self.db.get(SomDocument, uuid.UUID(str(doc_id)))
        if not doc:
            raise ValueError("Document not found")
        if doc.patient_id != pr.patient_id:
            raise ValueError("Document.patientId must match PreAuth.patientId")

        prov = ProvenanceService(self.db).create(activity="attach-document", author=None, correlation_id=correlation_id)
        link = SomPreAuthSupportingDocument(
            preauth_request_id=pr.id,
            document_id=doc.id,
            role=role,
            added_time=dt.datetime.now(dt.timezone.utc),
            correlation_id=correlation_id,
            provenance_id=prov.id,
            extensions={},
        )
        self.db.add(link)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.execute(
                    select(SomPreAuthSupportingDocument)
                    .where(SomPreAuthSupportingDocument.preauth_request_id == pr.id)
                    .where(SomPreAuthSupportingDocument.document_id == doc.id)
                    .where(SomPreAuthSupportingDocument.role == role)
                    .order_by(desc(SomPreAuthSupportingDocument.added_time))
                    .limit(1)
                )
                .scalar_one_or_none()
            )
            if existing:
                return {"id": str(existing.id), "preAuthId": str(pr.id), "documentId": str(doc.id), "role": role}
            raise
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type="PreAuthSupportingDocument",
            target_resource_id=str(link.id),
            target_som_table="som_preauth_supporting_document",
            target_som_id=str(link.id),
        )
        out = {"id": str(link.id), "preAuthId": str(pr.id), "documentId": str(doc.id), "role": role}
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type="PreAuthSupportingDocument",
            resource_id=link.id,
            som_table="som_preauth_supporting_document",
            som_id=link.id,
            request_payload=req,
            result_payload=out,
        )
        return out

    def get(self, preauth_id: str) -> dict[str, Any] | None:
        pr = self.db.get(SomPreAuthRequest, uuid.UUID(preauth_id))
        if not pr:
            return None
        latest_snapshot = (
            self.db.execute(
                select(SomPreAuthPackageSnapshot)
                .where(SomPreAuthPackageSnapshot.preauth_request_id == pr.id)
                .order_by(desc(SomPreAuthPackageSnapshot.created_time))
                .limit(1)
            )
            .scalar_one_or_none()
        )
        latest_decision = (
            self.db.execute(
                select(SomPreAuthDecision)
                .where(SomPreAuthDecision.preauth_request_id == pr.id)
                .order_by(desc(SomPreAuthDecision.decided_time))
                .limit(1)
            )
            .scalar_one_or_none()
        )
        docs = (
            self.db.execute(
                select(SomPreAuthSupportingDocument)
                .where(SomPreAuthSupportingDocument.preauth_request_id == pr.id)
                .order_by(SomPreAuthSupportingDocument.added_time.asc())
            )
            .scalars()
            .all()
        )
        return {
            "id": str(pr.id),
            "patientId": str(pr.patient_id),
            "encounterId": str(pr.encounter_id) if pr.encounter_id else None,
            "practitionerId": str(pr.practitioner_id),
            "organizationId": str(pr.organization_id) if pr.organization_id else None,
            "diagnosisConditionId": str(pr.diagnosis_condition_id),
            "serviceRequestId": str(pr.service_request_id),
            "status": pr.status,
            "priority": pr.priority,
            "payer": pr.payer,
            "policyId": pr.policy_id,
            "notes": pr.notes,
            "supportingObservationIds": pr.extensions.get("supportingObservationIds", []),
            "supportingDocumentIds": [str(d.document_id) for d in docs],
            "latestSnapshot": self._snapshot_dict(latest_snapshot) if latest_snapshot else None,
            "latestDecision": self._decision_dict(latest_decision) if latest_decision else None,
            "version": pr.version,
            "updatedTime": pr.updated_time.isoformat(),
            "createdTime": pr.created_time.isoformat(),
        }

    def search(self, *, patient_id: str | None, status: str | None, payer: str | None) -> dict[str, Any]:
        stmt = select(SomPreAuthRequest).order_by(desc(SomPreAuthRequest.updated_time)).limit(200)
        if patient_id:
            stmt = stmt.where(SomPreAuthRequest.patient_id == uuid.UUID(patient_id))
        if status:
            stmt = stmt.where(SomPreAuthRequest.status == status)
        if payer:
            stmt = stmt.where(SomPreAuthRequest.payer == payer)
        items = self.db.execute(stmt).scalars().all()
        return {"preauth": [self.get(str(i.id)) for i in items if self.get(str(i.id))]}

    def status_history(self, preauth_id: str) -> dict[str, Any]:
        pid = uuid.UUID(preauth_id)
        rows = (
            self.db.execute(
                select(SomPreAuthStatusHistory)
                .where(SomPreAuthStatusHistory.preauth_request_id == pid)
                .order_by(SomPreAuthStatusHistory.changed_time.asc())
            )
            .scalars()
            .all()
        )
        return {
            "history": [
                {
                    "fromStatus": r.from_status,
                    "toStatus": r.to_status,
                    "changedTime": r.changed_time.isoformat(),
                    "changedBy": r.changed_by,
                    "correlationId": r.correlation_id,
                    "provenanceId": str(r.provenance_id) if getattr(r, "provenance_id", None) else None,
                }
                for r in rows
            ]
        }

    def latest_decision(self, preauth_id: str) -> dict[str, Any] | None:
        pid = uuid.UUID(preauth_id)
        latest = (
            self.db.execute(
                select(SomPreAuthDecision)
                .where(SomPreAuthDecision.preauth_request_id == pid)
                .order_by(desc(SomPreAuthDecision.decided_time))
                .limit(1)
            )
            .scalar_one_or_none()
        )
        return self._decision_dict(latest) if latest else None

    def _status_change(
        self,
        preauth_id: uuid.UUID,
        *,
        from_status: str | None,
        to_status: str,
        changed_by: str,
        correlation_id: str | None,
        provenance_id: uuid.UUID | None,
    ) -> None:
        row = SomPreAuthStatusHistory(
            preauth_request_id=preauth_id,
            from_status=from_status,
            to_status=to_status,
            changed_time=dt.datetime.now(dt.timezone.utc),
            changed_by=changed_by,
            correlation_id=correlation_id,
            provenance_id=provenance_id,
            extensions={},
        )
        self.db.add(row)

    def _create_snapshot(self, pr: SomPreAuthRequest, *, correlation_id: str | None) -> SomPreAuthPackageSnapshot:
        prov = ProvenanceService(self.db).create(activity="snapshot", author=None, correlation_id=correlation_id)
        obs_ids = pr.extensions.get("supportingObservationIds") or []
        observations: list[dict[str, Any]] = []
        for oid in obs_ids:
            o = self.db.get(SomObservation, uuid.UUID(oid))
            if o:
                observations.append({"id": str(o.id), "codeConceptId": str(o.code_concept_id), "effectiveTime": o.effective_time.isoformat(), "status": o.status})
        doc_links = (
            self.db.execute(
                select(SomPreAuthSupportingDocument)
                .where(SomPreAuthSupportingDocument.preauth_request_id == pr.id)
                .order_by(SomPreAuthSupportingDocument.added_time.asc())
            )
            .scalars()
            .all()
        )
        documents: list[dict[str, Any]] = []
        for link in doc_links:
            d = self.db.get(SomDocument, link.document_id)
            if d:
                documents.append(
                    {
                        "id": str(d.id),
                        "typeConceptId": str(d.type_concept_id),
                        "dateTime": d.date_time.isoformat() if d.date_time else None,
                        "title": d.title,
                        "binaryId": str(d.binary_id) if d.binary_id else None,
                        "role": link.role,
                    }
                )
        snapshot_obj = {
            "schemaVersion": "1",
            "preAuthRequest": {"id": str(pr.id), "status": pr.status, "priority": pr.priority, "payer": pr.payer},
            "patient": {"id": str(pr.patient_id)},
            "encounter": {"id": str(pr.encounter_id)} if pr.encounter_id else None,
            "practitioner": {"id": str(pr.practitioner_id)},
            "organization": {"id": str(pr.organization_id)} if pr.organization_id else None,
            "diagnosisCondition": {"id": str(pr.diagnosis_condition_id)},
            "serviceRequest": {"id": str(pr.service_request_id)},
            "supportingObservations": observations,
            "supportingDocuments": documents,
        }
        canonical = json.dumps(snapshot_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        checksum = hashlib.sha256(canonical).hexdigest()
        snap = SomPreAuthPackageSnapshot(
            preauth_request_id=pr.id,
            created_time=dt.datetime.now(dt.timezone.utc),
            correlation_id=correlation_id,
            provenance_id=prov.id,
            schema_version="1",
            checksum=checksum,
            snapshot=snapshot_obj,
            extensions={},
        )
        self.db.add(snap)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type="PreAuthPackageSnapshot",
            target_resource_id=str(snap.id),
            target_som_table="som_preauth_package_snapshot",
            target_som_id=str(snap.id),
        )
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type="PreAuthPackageSnapshot",
            resource_id=snap.id,
            som_table="som_preauth_package_snapshot",
            som_id=snap.id,
            request_payload=None,
            result_payload={"snapshotId": str(snap.id), "preAuthId": str(pr.id), "checksum": checksum},
        )
        return snap

    @staticmethod
    def _snapshot_dict(s: SomPreAuthPackageSnapshot) -> dict[str, Any]:
        return {
            "id": str(s.id),
            "createdTime": s.created_time.isoformat(),
            "correlationId": s.correlation_id,
            "schemaVersion": s.schema_version,
            "checksum": s.checksum,
            "snapshot": s.snapshot,
            "provenanceId": str(s.provenance_id),
        }

    @staticmethod
    def _decision_dict(d: SomPreAuthDecision) -> dict[str, Any]:
        return {
            "id": str(d.id),
            "decidedTime": d.decided_time.isoformat(),
            "outcome": d.outcome,
            "reasonCodes": d.reason_codes,
            "rationale": d.rationale,
            "requestedAdditionalInfo": d.requested_additional_info,
            "provenanceId": str(d.provenance_id),
        }


def _uuid(v: Any) -> uuid.UUID:
    if not v:
        raise ValueError("Missing required id")
    return uuid.UUID(str(v))
