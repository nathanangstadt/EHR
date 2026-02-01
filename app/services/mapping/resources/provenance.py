from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import SomProvenance
from app.services.mapping.fhir_utils import bundle, to_uuid
from app.services.mapping.resources.base import BaseMapper


class ProvenanceMapper(BaseMapper):
    resource_type = "Provenance"

    def create(self, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        raise ValueError("Provenance creation is system-managed in this sample")

    def read(self, id: str) -> dict[str, Any] | None:
        p = self.db.get(SomProvenance, to_uuid(id))
        return self._to_fhir(p) if p else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        raise ValueError("Provenance update not supported")

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomProvenance)
        cid = params.get("correlationId") or params.get("correlation-id")
        if cid:
            stmt = stmt.where(SomProvenance.correlation_id == cid)
        stmt = stmt.limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(i) for i in items], total=len(items))

    def _to_fhir(self, p: SomProvenance) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": "Provenance",
            "id": str(p.id),
            "recorded": p.recorded_time.isoformat().replace("+00:00", "Z"),
            "activity": {"text": p.activity},
            "agent": [
                {
                    "who": {"display": p.agent_display or p.author or "system"},
                    "type": {"text": p.agent_type or p.source_system},
                }
            ],
        }
        if p.target_resource_type and p.target_resource_id:
            out["target"] = [{"reference": f"{p.target_resource_type}/{p.target_resource_id}"}]
        ext: list[dict[str, Any]] = []
        if p.correlation_id:
            ext.append({"url": "correlationId", "valueString": p.correlation_id})
        if p.source_system:
            ext.append({"url": "sourceSystem", "valueString": p.source_system})
        if p.original_record_ref:
            ext.append({"url": "originalRecordRef", "valueString": p.original_record_ref})
        if p.target_som_table or p.target_som_id:
            ext.append(
                {
                    "url": "somTarget",
                    "valueString": f"{p.target_som_table}:{p.target_som_id}" if p.target_som_table and p.target_som_id else (p.target_som_table or str(p.target_som_id)),
                }
            )
        if ext:
            out["extension"] = ext
        return out
