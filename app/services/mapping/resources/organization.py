from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import SomOrganization
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService


class OrganizationMapper(BaseMapper):
    resource_type = "Organization"

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
        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        org = SomOrganization(
            name=body.get("name"),
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(org)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type=self.resource_type,
            target_resource_id=str(org.id),
            target_som_table="som_organization",
            target_som_id=str(org.id),
        )
        out = self._to_fhir(org)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=org.id,
            som_table="som_organization",
            som_id=org.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        org = self.db.get(SomOrganization, to_uuid(id))
        return self._to_fhir(org) if org else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        org = self.db.get(SomOrganization, to_uuid(id))
        if not org:
            return None
        prov = ProvenanceService(self.db).create(
            activity="update",
            author=None,
            correlation_id=correlation_id,
            target_resource_type=self.resource_type,
            target_resource_id=str(org.id),
            target_som_table="som_organization",
            target_som_id=str(org.id),
        )
        org.name = body.get("name")
        org.version += 1
        org.updated_provenance_id = prov.id
        org.extensions = org.extensions or {}
        out = self._to_fhir(org)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=org.id,
            som_table="som_organization",
            som_id=org.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomOrganization).limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(o) for o in items], total=len(items))

    def _to_fhir(self, o: SomOrganization) -> dict[str, Any]:
        return {
            "resourceType": self.resource_type,
            "id": str(o.id),
            "meta": fhir_meta(version=o.version, last_updated=o.updated_time),
            "name": o.name,
        }
