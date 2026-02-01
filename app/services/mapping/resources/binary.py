from __future__ import annotations

import base64
import datetime as dt
import hashlib
from typing import Any

from sqlalchemy import select

from app.db.models import SomBinary
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService


class BinaryMapper(BaseMapper):
    resource_type = "Binary"

    def create(self, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        content_type = body.get("contentType") or body.get("content-type")
        data_b64 = body.get("data")
        if not content_type:
            raise ValueError("Binary.contentType required")
        if not data_b64:
            raise ValueError("Binary.data required (base64)")
        try:
            data = base64.b64decode(data_b64)
        except Exception:
            raise ValueError("Binary.data must be base64")
        sha = hashlib.sha256(data).hexdigest()

        if correlation_id:
            req = {"contentType": str(content_type), "sha256": sha}
            prior = AuditService(self.db).find_idempotent_result(
                correlation_id=correlation_id,
                operation="create",
                resource_type=self.resource_type,
                request_payload=req,
            )
            if prior:
                return prior

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        b = SomBinary(
            content_type=str(content_type),
            data=data,
            size_bytes=len(data),
            sha256_hex=sha,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(b)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type=self.resource_type,
            target_resource_id=str(b.id),
            target_som_table="som_binary",
            target_som_id=str(b.id),
        )

        out = self._to_fhir(b, include_data=False)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=b.id,
            som_table="som_binary",
            som_id=b.id,
            request_payload={"contentType": str(content_type), "sha256": sha},
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        b = self.db.get(SomBinary, to_uuid(id))
        return self._to_fhir(b, include_data=True) if b else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        b = self.db.get(SomBinary, to_uuid(id))
        if not b:
            return None
        content_type = body.get("contentType") or b.content_type
        data_b64 = body.get("data")
        if data_b64:
            try:
                data = base64.b64decode(data_b64)
            except Exception:
                raise ValueError("Binary.data must be base64")
            b.data = data
            b.size_bytes = len(data)
            b.sha256_hex = hashlib.sha256(data).hexdigest()
        b.content_type = str(content_type)
        prov = ProvenanceService(self.db).create(
            activity="update",
            author=None,
            correlation_id=correlation_id,
            target_resource_type=self.resource_type,
            target_resource_id=str(b.id),
            target_som_table="som_binary",
            target_som_id=str(b.id),
        )
        b.version += 1
        b.updated_provenance_id = prov.id
        out = self._to_fhir(b, include_data=False)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type=self.resource_type,
            resource_id=b.id,
            som_table="som_binary",
            som_id=b.id,
            request_payload={"contentType": content_type, "hasData": bool(data_b64)},
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        sha = params.get("sha256")
        stmt = select(SomBinary)
        if sha:
            stmt = stmt.where(SomBinary.sha256_hex == sha)
        stmt = stmt.limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(i, include_data=False) for i in items], total=len(items))

    def _to_fhir(self, b: SomBinary, *, include_data: bool) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(b.id),
            "meta": fhir_meta(version=b.version, last_updated=b.updated_time),
            "contentType": b.content_type,
        }
        if include_data:
            out["data"] = base64.b64encode(b.data).decode("ascii")
        return out
