from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    SomBinary,
    SomConcept,
    SomCondition,
    SomDocument,
    SomEncounter,
    SomObservation,
    SomObservationVersion,
    SomPatient,
    SomServiceRequest,
    SomServiceRequestReason,
)


class InternalService:
    def __init__(self, db: Session):
        self.db = db

    def som_backing(self, resource_type: str, id: str) -> dict[str, Any] | None:
        rt = resource_type.lower()
        rid = uuid.UUID(id)

        if rt == "binary":
            b = self.db.get(SomBinary, rid)
            return {"table": "som_binary", "row": self._row(b)} if b else None
        if rt == "documentreference":
            d = self.db.get(SomDocument, rid)
            if not d:
                return None
            concept = self.db.get(SomConcept, d.type_concept_id)
            return {
                "table": "som_document",
                "row": self._row(d),
                "typeConcept": self._concept(concept),
            }
        if rt == "patient":
            p = self.db.get(SomPatient, rid)
            return {"table": "som_patient", "row": self._row(p)} if p else None
        if rt == "encounter":
            e = self.db.get(SomEncounter, rid)
            return {"table": "som_encounter", "row": self._row(e)} if e else None
        if rt == "condition":
            c = self.db.get(SomCondition, rid)
            if not c:
                return None
            concept = self.db.get(SomConcept, c.code_concept_id)
            return {"table": "som_condition", "row": self._row(c), "codeConcept": self._concept(concept)}
        if rt == "servicerequest":
            sr = self.db.get(SomServiceRequest, rid)
            if not sr:
                return None
            concept = self.db.get(SomConcept, sr.code_concept_id)
            reasons = (
                self.db.execute(
                    select(SomServiceRequestReason)
                    .where(SomServiceRequestReason.service_request_id == sr.id)
                    .order_by(SomServiceRequestReason.rank.asc())
                )
                .scalars()
                .all()
            )
            return {
                "table": "som_service_request",
                "row": self._row(sr),
                "codeConcept": self._concept(concept),
                "reasonConditionIds": [str(r.condition_id) for r in reasons],
            }
        if rt == "observation":
            o = self.db.get(SomObservation, rid)
            if not o:
                return None
            code = self.db.get(SomConcept, o.code_concept_id)
            val = self.db.get(SomConcept, o.value_concept_id) if o.value_concept_id else None
            return {
                "table": "som_observation",
                "row": self._row(o),
                "codeConcept": self._concept(code),
                "valueConcept": self._concept(val) if val else None,
            }
        return None

    def observation_versions(self, id: str) -> dict[str, Any] | None:
        oid = uuid.UUID(id)
        obs = self.db.get(SomObservation, oid)
        if not obs:
            return None
        versions = (
            self.db.execute(
                select(SomObservationVersion)
                .where(SomObservationVersion.observation_id == obs.id)
                .order_by(SomObservationVersion.version.asc())
            )
            .scalars()
            .all()
        )

        def to_simple(v: SomObservationVersion) -> dict[str, Any]:
            return {
                "version": v.version,
                "recordedTime": v.recorded_time.isoformat(),
                "status": v.status,
                "category": v.category,
                "effectiveTime": v.effective_time.isoformat(),
                "valueType": v.value_type,
                "valueQuantity": {
                    "value": float(v.value_quantity_value) if v.value_quantity_value is not None else None,
                    "unit": v.value_quantity_unit,
                }
                if v.value_type == "quantity"
                else None,
                "valueConceptId": str(v.value_concept_id) if v.value_concept_id else None,
            }

        simple = [to_simple(v) for v in versions]
        diffs: list[dict[str, Any]] = []
        prev: dict[str, Any] | None = None
        for cur in simple:
            if prev is None:
                diffs.append({"version": cur["version"], "changed": []})
            else:
                changed = [k for k in ("status", "category", "effectiveTime", "valueType", "valueQuantity", "valueConceptId") if prev.get(k) != cur.get(k)]
                diffs.append({"version": cur["version"], "changed": changed})
            prev = cur
        return {"observationId": str(obs.id), "versions": simple, "diffs": diffs}

    @staticmethod
    def _row(obj) -> dict[str, Any]:
        if obj is None:
            return {}
        data = {}
        for col in obj.__table__.columns:  # type: ignore[attr-defined]
            v = getattr(obj, col.name)
            if isinstance(v, uuid.UUID):
                data[col.name] = str(v)
            elif hasattr(v, "isoformat"):
                data[col.name] = v.isoformat()
            else:
                data[col.name] = v
        return data

    @staticmethod
    def _concept(c: SomConcept | None) -> dict[str, Any] | None:
        if not c:
            return None
        return {
            "id": str(c.id),
            "system": c.code_system.system_uri,
            "code": c.code,
            "display": c.display,
            "version": c.version_string,
        }
