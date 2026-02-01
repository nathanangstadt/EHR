from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import or_, select

from app.db.models import SomPatient
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService


class PatientMapper(BaseMapper):
    resource_type = "Patient"

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

        identifier = (body.get("identifier") or [{}])[0]
        name = (body.get("name") or [{}])[0]
        birth_date = body.get("birthDate")
        bd = dt.date.fromisoformat(birth_date) if birth_date else None

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        patient = SomPatient(
            identifier_system=identifier.get("system"),
            identifier_value=identifier.get("value"),
            name_family=name.get("family"),
            name_given=(name.get("given") or [None])[0],
            birth_date=bd,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(patient)
        self.db.flush()

        out = self._to_fhir(patient)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            resource_type=self.resource_type,
            resource_id=patient.id,
            som_table="som_patient",
            som_id=patient.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        patient = self.db.get(SomPatient, to_uuid(id))
        return self._to_fhir(patient) if patient else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        if correlation_id:
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="update",
                resource_type=self.resource_type,
                request_payload=body,
            )
            if prior and prior.get("id") == id:
                return prior

        patient = self.db.get(SomPatient, to_uuid(id))
        if not patient:
            return None

        identifier = (body.get("identifier") or [{}])[0]
        name = (body.get("name") or [{}])[0]
        birth_date = body.get("birthDate")
        bd = dt.date.fromisoformat(birth_date) if birth_date else None

        prov = ProvenanceService(self.db).create(activity="update", author=None, correlation_id=correlation_id)
        patient.identifier_system = identifier.get("system")
        patient.identifier_value = identifier.get("value")
        patient.name_family = name.get("family")
        patient.name_given = (name.get("given") or [None])[0]
        patient.birth_date = bd
        patient.version += 1
        patient.updated_provenance_id = prov.id
        patient.extensions = patient.extensions or {}

        out = self._to_fhir(patient)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            resource_type=self.resource_type,
            resource_id=patient.id,
            som_table="som_patient",
            som_id=patient.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomPatient)

        identifier = params.get("identifier")
        if identifier:
            if "|" in identifier:
                system, value = identifier.split("|", 1)
                stmt = stmt.where(SomPatient.identifier_system == system).where(SomPatient.identifier_value == value)
            else:
                stmt = stmt.where(SomPatient.identifier_value == identifier)

        name = params.get("name")
        if name:
            like = f"%{name}%"
            stmt = stmt.where(or_(SomPatient.name_family.ilike(like), SomPatient.name_given.ilike(like)))

        birthdate = params.get("birthdate")
        if birthdate:
            stmt = stmt.where(SomPatient.birth_date == dt.date.fromisoformat(birthdate))

        stmt = stmt.limit(count)
        patients = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(p) for p in patients], total=len(patients))

    def _to_fhir(self, p: SomPatient) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(p.id),
            "meta": fhir_meta(version=p.version, last_updated=p.updated_time),
        }
        if p.identifier_value:
            out["identifier"] = [{"system": p.identifier_system, "value": p.identifier_value}]
        if p.name_family or p.name_given:
            out["name"] = [{"family": p.name_family, "given": [p.name_given] if p.name_given else []}]
        if p.birth_date:
            out["birthDate"] = p.birth_date.isoformat()
        return out
