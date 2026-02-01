from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import desc, select

from app.db.models import SomBinary, SomDocument, SomPatient
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, parse_reference, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService
from app.services.terminology import TerminologyService


def _parse_dt(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


class DocumentReferenceMapper(BaseMapper):
    resource_type = "DocumentReference"

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

        status = body.get("status") or "current"
        type_cc = body.get("type") or {}
        coding = TerminologyService.pick_coding(type_cc)
        type_concept = TerminologyService(self.db).normalize_concept(
            system=coding["system"],
            code=coding["code"],
            display=coding.get("display"),
            version=coding.get("version"),
            correlation_id=correlation_id,
        )

        date_time = body.get("date")
        doc_dt = _parse_dt(date_time) if date_time else None
        title = body.get("description") or body.get("title")

        # Resolve attachment: accept url=Binary/{id} or inline base64 data (handled by Binary POST first).
        content = (body.get("content") or [{}])[0]
        attachment = content.get("attachment") or {}
        binary_id = None
        url = attachment.get("url")
        if url and isinstance(url, str) and url.startswith("Binary/"):
            binary_id = to_uuid(url.split("/", 1)[1])
            if not self.db.get(SomBinary, binary_id):
                raise ValueError("Binary not found for attachment.url")

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        doc = SomDocument(
            patient_id=patient.id,
            encounter_id=None,
            status=status,
            type_concept_id=type_concept.id,
            date_time=doc_dt,
            title=title,
            description=body.get("description"),
            binary_id=binary_id,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(doc)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type=self.resource_type,
            target_resource_id=str(doc.id),
            target_som_table="som_document",
            target_som_id=str(doc.id),
        )

        out = self._to_fhir(doc)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=doc.id,
            som_table="som_document",
            som_id=doc.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        doc = self.db.get(SomDocument, to_uuid(id))
        return self._to_fhir(doc) if doc else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        doc = self.db.get(SomDocument, to_uuid(id))
        if not doc:
            return None

        status = body.get("status") or doc.status
        type_cc = body.get("type") or {}
        coding = TerminologyService.pick_coding(type_cc)
        type_concept = TerminologyService(self.db).normalize_concept(
            system=coding["system"],
            code=coding["code"],
            display=coding.get("display"),
            version=coding.get("version"),
            correlation_id=correlation_id,
        )

        date_time = body.get("date")
        doc_dt = _parse_dt(date_time) if date_time else doc.date_time
        title = body.get("description") or body.get("title") or doc.title

        content = (body.get("content") or [{}])[0]
        attachment = content.get("attachment") or {}
        url = attachment.get("url")
        if url and isinstance(url, str) and url.startswith("Binary/"):
            bid = to_uuid(url.split("/", 1)[1])
            if not self.db.get(SomBinary, bid):
                raise ValueError("Binary not found for attachment.url")
            doc.binary_id = bid

        prov = ProvenanceService(self.db).create(
            activity="update",
            author=None,
            correlation_id=correlation_id,
            target_resource_type=self.resource_type,
            target_resource_id=str(doc.id),
            target_som_table="som_document",
            target_som_id=str(doc.id),
        )
        doc.status = status
        doc.type_concept_id = type_concept.id
        doc.date_time = doc_dt
        doc.title = title
        doc.description = body.get("description") or doc.description
        doc.version += 1
        doc.updated_provenance_id = prov.id

        out = self._to_fhir(doc)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=doc.id,
            som_table="som_document",
            som_id=doc.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomDocument)
        patient = params.get("patient")
        if patient:
            pid = patient.split("/")[-1]
            stmt = stmt.where(SomDocument.patient_id == to_uuid(pid))
        date_param = params.get("date")
        if date_param:
            parts = date_param if isinstance(date_param, list) else [date_param]
            for p in parts:
                if p.startswith("ge"):
                    stmt = stmt.where(SomDocument.date_time >= _parse_dt(p[2:]))
                if p.startswith("le"):
                    stmt = stmt.where(SomDocument.date_time <= _parse_dt(p[2:]))
        type_param = params.get("type")
        if type_param:
            if "|" in type_param:
                system, code = type_param.split("|", 1)
                from app.db.models import SomCodeSystem, SomConcept

                sub = (
                    select(SomConcept.id)
                    .join(SomCodeSystem, SomConcept.code_system_id == SomCodeSystem.id)
                    .where(SomCodeSystem.system_uri == system)
                    .where(SomConcept.code == code)
                )
                stmt = stmt.where(SomDocument.type_concept_id.in_(sub))
        # Postgres expects: "date_time DESC NULLS LAST" (not "date_time NULLS LAST DESC").
        stmt = stmt.order_by(SomDocument.date_time.desc().nullslast(), SomDocument.updated_time.desc()).limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(d) for d in items], total=len(items))

    def _to_fhir(self, doc: SomDocument) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(doc.id),
            "meta": fhir_meta(version=doc.version, last_updated=doc.updated_time),
            "status": doc.status,
            "subject": {"reference": f"Patient/{doc.patient_id}"},
            "type": {
                "coding": [
                    {
                        "system": doc.type_concept.code_system.system_uri,
                        "code": doc.type_concept.code,
                        "display": doc.type_concept.display,
                    }
                ]
            },
        }
        if doc.date_time:
            out["date"] = doc.date_time.isoformat().replace("+00:00", "Z")
        if doc.description:
            out["description"] = doc.description
        if doc.binary_id:
            out["content"] = [{"attachment": {"url": f"Binary/{doc.binary_id}", "contentType": doc.binary.content_type if doc.binary else None}}]
        return out
