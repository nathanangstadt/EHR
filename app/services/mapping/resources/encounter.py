from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select

from app.db.models import SomEncounter, SomPatient
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, parse_reference, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService


class EncounterMapper(BaseMapper):
    resource_type = "Encounter"

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

        period = body.get("period") or {}
        start = period.get("start")
        end = period.get("end")
        start_dt = dt.datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
        end_dt = dt.datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        enc = SomEncounter(
            patient_id=patient.id,
            status=body.get("status"),
            start_time=start_dt,
            end_time=end_dt,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(enc)
        self.db.flush()
        out = self._to_fhir(enc)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            resource_type=self.resource_type,
            resource_id=enc.id,
            som_table="som_encounter",
            som_id=enc.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        enc = self.db.get(SomEncounter, to_uuid(id))
        return self._to_fhir(enc) if enc else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        enc = self.db.get(SomEncounter, to_uuid(id))
        if not enc:
            return None
        period = body.get("period") or {}
        start = period.get("start")
        end = period.get("end")
        start_dt = dt.datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
        end_dt = dt.datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None

        prov = ProvenanceService(self.db).create(activity="update", author=None, correlation_id=correlation_id)
        enc.status = body.get("status")
        enc.start_time = start_dt
        enc.end_time = end_dt
        enc.version += 1
        enc.updated_provenance_id = prov.id
        enc.extensions = enc.extensions or {}
        out = self._to_fhir(enc)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            resource_type=self.resource_type,
            resource_id=enc.id,
            som_table="som_encounter",
            som_id=enc.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomEncounter)
        patient = params.get("patient")
        if patient:
            pid = patient.split("/")[-1]
            stmt = stmt.where(SomEncounter.patient_id == to_uuid(pid))
        status = params.get("status")
        if status:
            stmt = stmt.where(SomEncounter.status == status)
        # date range: date=ge... and/or date=le...
        date_param = params.get("date")
        if date_param:
            parts = date_param if isinstance(date_param, list) else [date_param]
            for p in parts:
                if p.startswith("ge"):
                    d = dt.datetime.fromisoformat(p[2:].replace("Z", "+00:00"))
                    stmt = stmt.where(SomEncounter.start_time >= d)
                if p.startswith("le"):
                    d = dt.datetime.fromisoformat(p[2:].replace("Z", "+00:00"))
                    stmt = stmt.where(SomEncounter.start_time <= d)
        stmt = stmt.limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(i) for i in items], total=len(items))

    def _to_fhir(self, e: SomEncounter) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(e.id),
            "meta": fhir_meta(version=e.version, last_updated=e.updated_time),
            "subject": {"reference": f"Patient/{e.patient_id}"},
        }
        if e.status:
            out["status"] = e.status
        period: dict[str, Any] = {}
        if e.start_time:
            period["start"] = e.start_time.isoformat().replace("+00:00", "Z")
        if e.end_time:
            period["end"] = e.end_time.isoformat().replace("+00:00", "Z")
        if period:
            out["period"] = period
        return out
