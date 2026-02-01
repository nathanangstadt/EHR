from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import delete, select

from app.db.models import SomCondition, SomEncounter, SomPatient, SomServiceRequest, SomServiceRequestReason
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, parse_reference, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService
from app.services.terminology import TerminologyService


class ServiceRequestMapper(BaseMapper):
    resource_type = "ServiceRequest"

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

        authored_on = body.get("authoredOn")
        authored_dt = dt.datetime.fromisoformat(authored_on.replace("Z", "+00:00")) if authored_on else None

        encounter_id = None
        if body.get("encounter", {}).get("reference"):
            rt, rid = parse_reference(body["encounter"]["reference"])
            if rt != "Encounter":
                raise ValueError("ServiceRequest.encounter must reference Encounter")
            encounter_id = to_uuid(rid)
            enc = self.db.get(SomEncounter, encounter_id)
            if not enc:
                raise ValueError("Encounter not found")
            if enc.patient_id != patient.id:
                raise ValueError("Encounter.patient must match ServiceRequest.patient")

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        sr = SomServiceRequest(
            patient_id=patient.id,
            encounter_id=encounter_id,
            code_concept_id=concept.id,
            status=body.get("status"),
            intent=body.get("intent"),
            priority=body.get("priority"),
            authored_on=authored_dt,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(sr)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type=self.resource_type,
            target_resource_id=str(sr.id),
            target_som_table="som_service_request",
            target_som_id=str(sr.id),
        )

        self._sync_reasons(sr, body, provenance_id=prov.id)
        out = self._to_fhir(sr, concept_system=concept.code_system.system_uri, concept_code=concept.code, concept_display=concept.display)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=sr.id,
            som_table="som_service_request",
            som_id=sr.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        sr = self.db.get(SomServiceRequest, to_uuid(id))
        if not sr:
            return None
        concept = sr.code_concept
        return self._to_fhir(sr, concept_system=concept.code_system.system_uri, concept_code=concept.code, concept_display=concept.display)

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        sr = self.db.get(SomServiceRequest, to_uuid(id))
        if not sr:
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
        authored_on = body.get("authoredOn")
        authored_dt = dt.datetime.fromisoformat(authored_on.replace("Z", "+00:00")) if authored_on else None
        encounter_id = sr.encounter_id
        if body.get("encounter", {}).get("reference"):
            rt, rid = parse_reference(body["encounter"]["reference"])
            if rt != "Encounter":
                raise ValueError("ServiceRequest.encounter must reference Encounter")
            encounter_id = to_uuid(rid)
            enc = self.db.get(SomEncounter, encounter_id)
            if not enc:
                raise ValueError("Encounter not found")
            if enc.patient_id != sr.patient_id:
                raise ValueError("Encounter.patient must match ServiceRequest.patient")
        prov = ProvenanceService(self.db).create(
            activity="update",
            author=None,
            correlation_id=correlation_id,
            target_resource_type=self.resource_type,
            target_resource_id=str(sr.id),
            target_som_table="som_service_request",
            target_som_id=str(sr.id),
        )
        sr.code_concept_id = concept.id
        sr.status = body.get("status")
        sr.intent = body.get("intent")
        sr.priority = body.get("priority")
        sr.authored_on = authored_dt
        sr.encounter_id = encounter_id
        sr.version += 1
        sr.updated_provenance_id = prov.id
        sr.extensions = sr.extensions or {}
        self._sync_reasons(sr, body, provenance_id=prov.id)
        out = self._to_fhir(sr, concept_system=concept.code_system.system_uri, concept_code=concept.code, concept_display=concept.display)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=sr.id,
            som_table="som_service_request",
            som_id=sr.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomServiceRequest)
        patient = params.get("patient")
        if patient:
            pid = patient.split("/")[-1]
            stmt = stmt.where(SomServiceRequest.patient_id == to_uuid(pid))
        status = params.get("status")
        if status:
            stmt = stmt.where(SomServiceRequest.status == status)
        code = params.get("code")
        if code:
            from app.db.models import SomCodeSystem, SomConcept

            if "|" in code:
                system, c = code.split("|", 1)
                sub = (
                    select(SomConcept.id)
                    .join(SomCodeSystem, SomConcept.code_system_id == SomCodeSystem.id)
                    .where(SomCodeSystem.system_uri == system)
                    .where(SomConcept.code == c)
                )
            else:
                sub = select(SomConcept.id).where(SomConcept.code == code)
            stmt = stmt.where(SomServiceRequest.code_concept_id.in_(sub))
        authored = params.get("authored")
        if authored:
            parts = authored if isinstance(authored, list) else [authored]
            for p in parts:
                if p.startswith("ge"):
                    d = dt.datetime.fromisoformat(p[2:].replace("Z", "+00:00"))
                    stmt = stmt.where(SomServiceRequest.authored_on >= d)
                if p.startswith("le"):
                    d = dt.datetime.fromisoformat(p[2:].replace("Z", "+00:00"))
                    stmt = stmt.where(SomServiceRequest.authored_on <= d)
        stmt = stmt.limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self.read(str(i.id)) for i in items if self.read(str(i.id))], total=len(items))

    def _to_fhir(self, sr: SomServiceRequest, *, concept_system: str, concept_code: str, concept_display: str | None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(sr.id),
            "meta": fhir_meta(version=sr.version, last_updated=sr.updated_time),
            "subject": {"reference": f"Patient/{sr.patient_id}"},
            "code": {"coding": [{"system": concept_system, "code": concept_code, "display": concept_display}]},
        }
        if sr.status:
            out["status"] = sr.status
        if sr.intent:
            out["intent"] = sr.intent
        if sr.priority:
            out["priority"] = sr.priority
        if sr.authored_on:
            out["authoredOn"] = sr.authored_on.isoformat().replace("+00:00", "Z")
        if sr.encounter_id:
            out["encounter"] = {"reference": f"Encounter/{sr.encounter_id}"}

        reasons = (
            self.db.execute(
                select(SomServiceRequestReason)
                .where(SomServiceRequestReason.service_request_id == sr.id)
                .order_by(SomServiceRequestReason.rank.asc())
            )
            .scalars()
            .all()
        )
        if reasons:
            out["reasonReference"] = [{"reference": f"Condition/{r.condition_id}"} for r in reasons]
        return out

    def _sync_reasons(self, sr: SomServiceRequest, body: dict[str, Any], *, provenance_id) -> None:
        refs = body.get("reasonReference") or []
        condition_ids: list[str] = []
        for r in refs:
            ref = (r or {}).get("reference")
            if not ref:
                continue
            rt, rid = parse_reference(ref)
            if rt != "Condition":
                continue
            condition_ids.append(rid)

        # Replace existing reasons.
        self.db.execute(delete(SomServiceRequestReason).where(SomServiceRequestReason.service_request_id == sr.id))

        rank = 1
        for cid in condition_ids:
            cond = self.db.get(SomCondition, to_uuid(cid))
            if not cond:
                raise ValueError("Condition not found for reasonReference")
            if cond.patient_id != sr.patient_id:
                raise ValueError("Condition.patient must match ServiceRequest.patient")
            link = SomServiceRequestReason(
                service_request_id=sr.id,
                condition_id=cond.id,
                role="reason",
                rank=rank,
                created_provenance_id=provenance_id,
                updated_provenance_id=None,
                extensions={},
            )
            self.db.add(link)
            rank += 1
