from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select

from app.db.models import SomCondition, SomPatient
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, parse_reference, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService
from app.services.terminology import TerminologyService


class ConditionMapper(BaseMapper):
    resource_type = "Condition"

    def create(self, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        if correlation_id:
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="create",
                resource_type=self.resource_type,
                request_payload=body,
            )
            if prior:
                return prior
        subject = body.get("subject") or {}
        _, patient_id = parse_reference(subject.get("reference", ""))
        patient = self.db.get(SomPatient, to_uuid(patient_id))
        if not patient:
            raise ValueError("Patient not found")

        code_cc = body.get("code") or {}
        coding = TerminologyService.pick_coding(code_cc)
        concept = TerminologyService(self.db).normalize_concept(
            system=coding["system"],
            code=coding["code"],
            display=coding.get("display"),
            version=coding.get("version"),
            correlation_id=correlation_id,
        )

        clinical_status = None
        if body.get("clinicalStatus", {}).get("coding"):
            clinical_status = body["clinicalStatus"]["coding"][0].get("code")

        onset = body.get("onsetDateTime") or body.get("onsetDate")
        onset_date = dt.date.fromisoformat(onset[:10]) if onset else None

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        c = SomCondition(
            patient_id=patient.id,
            code_concept_id=concept.id,
            clinical_status=clinical_status,
            onset_date=onset_date,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(c)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type=self.resource_type,
            target_resource_id=str(c.id),
            target_som_table="som_condition",
            target_som_id=str(c.id),
        )
        out = self._to_fhir(c, concept_system=concept.code_system.system_uri, concept_code=concept.code, concept_display=concept.display)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=c.id,
            som_table="som_condition",
            som_id=c.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        c = self.db.get(SomCondition, to_uuid(id))
        if not c:
            return None
        concept = c.code_concept
        return self._to_fhir(c, concept_system=concept.code_system.system_uri, concept_code=concept.code, concept_display=concept.display)

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        c = self.db.get(SomCondition, to_uuid(id))
        if not c:
            return None
        code_cc = body.get("code") or {}
        coding = TerminologyService.pick_coding(code_cc)
        concept = TerminologyService(self.db).normalize_concept(
            system=coding["system"],
            code=coding["code"],
            display=coding.get("display"),
            version=coding.get("version"),
            correlation_id=correlation_id,
        )
        clinical_status = None
        if body.get("clinicalStatus", {}).get("coding"):
            clinical_status = body["clinicalStatus"]["coding"][0].get("code")
        onset = body.get("onsetDateTime") or body.get("onsetDate")
        onset_date = dt.date.fromisoformat(onset[:10]) if onset else None
        prov = ProvenanceService(self.db).create(
            activity="update",
            author=None,
            correlation_id=correlation_id,
            target_resource_type=self.resource_type,
            target_resource_id=str(c.id),
            target_som_table="som_condition",
            target_som_id=str(c.id),
        )
        c.code_concept_id = concept.id
        c.clinical_status = clinical_status
        c.onset_date = onset_date
        c.version += 1
        c.updated_provenance_id = prov.id
        c.extensions = c.extensions or {}
        out = self._to_fhir(c, concept_system=concept.code_system.system_uri, concept_code=concept.code, concept_display=concept.display)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=c.id,
            som_table="som_condition",
            som_id=c.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomCondition)
        patient = params.get("patient")
        if patient:
            pid = patient.split("/")[-1]
            stmt = stmt.where(SomCondition.patient_id == to_uuid(pid))
        clinical_status = params.get("clinical-status")
        if clinical_status:
            stmt = stmt.where(SomCondition.clinical_status == clinical_status)
        code = params.get("code")
        if code:
            # system|code or code
            if "|" in code:
                system, c = code.split("|", 1)
                # join concept/code system is expensive; keep simple: filter by concept id matching these via subquery
                from app.db.models import SomCodeSystem, SomConcept

                sub = (
                    select(SomConcept.id)
                    .join(SomCodeSystem, SomConcept.code_system_id == SomCodeSystem.id)
                    .where(SomCodeSystem.system_uri == system)
                    .where(SomConcept.code == c)
                )
                stmt = stmt.where(SomCondition.code_concept_id.in_(sub))
            else:
                from app.db.models import SomConcept

                sub = select(SomConcept.id).where(SomConcept.code == code)
                stmt = stmt.where(SomCondition.code_concept_id.in_(sub))
        stmt = stmt.limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self.read(str(i.id)) for i in items if self.read(str(i.id))], total=len(items))

    def _to_fhir(self, c: SomCondition, *, concept_system: str, concept_code: str, concept_display: str | None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(c.id),
            "meta": fhir_meta(version=c.version, last_updated=c.updated_time),
            "subject": {"reference": f"Patient/{c.patient_id}"},
            "code": {"coding": [{"system": concept_system, "code": concept_code, "display": concept_display}]},
        }
        if c.clinical_status:
            out["clinicalStatus"] = {"coding": [{"code": c.clinical_status}]}
        if c.onset_date:
            out["onsetDate"] = c.onset_date.isoformat()
        return out
