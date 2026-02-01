from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import SomPractitioner
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService


class PractitionerMapper(BaseMapper):
    resource_type = "Practitioner"

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

        name = (body.get("name") or [{}])[0]
        display = name.get("text") or " ".join((name.get("given") or []) + ([name.get("family")] if name.get("family") else []))

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        pr = SomPractitioner(name=display, created_provenance_id=prov.id, updated_provenance_id=None, extensions={})
        self.db.add(pr)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type=self.resource_type,
            target_resource_id=str(pr.id),
            target_som_table="som_practitioner",
            target_som_id=str(pr.id),
        )
        out = self._to_fhir(pr)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=pr.id,
            som_table="som_practitioner",
            som_id=pr.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        pr = self.db.get(SomPractitioner, to_uuid(id))
        return self._to_fhir(pr) if pr else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        pr = self.db.get(SomPractitioner, to_uuid(id))
        if not pr:
            return None
        prov = ProvenanceService(self.db).create(
            activity="update",
            author=None,
            correlation_id=correlation_id,
            target_resource_type=self.resource_type,
            target_resource_id=str(pr.id),
            target_som_table="som_practitioner",
            target_som_id=str(pr.id),
        )
        name = (body.get("name") or [{}])[0]
        display = name.get("text") or " ".join((name.get("given") or []) + ([name.get("family")] if name.get("family") else []))
        pr.name = display
        pr.version += 1
        pr.updated_provenance_id = prov.id
        pr.extensions = pr.extensions or {}
        out = self._to_fhir(pr)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=pr.id,
            som_table="som_practitioner",
            som_id=pr.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomPractitioner).limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(p) for p in items], total=len(items))

    def _to_fhir(self, p: SomPractitioner) -> dict[str, Any]:
        return {
            "resourceType": self.resource_type,
            "id": str(p.id),
            "meta": fhir_meta(version=p.version, last_updated=p.updated_time),
            "name": [{"text": p.name}],
        }
