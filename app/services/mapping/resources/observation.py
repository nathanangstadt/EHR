from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select

from app.db.models import SomConcept, SomEncounter, SomObservation, SomObservationVersion, SomPatient
from app.services.audit import AuditService
from app.services.mapping.fhir_utils import bundle, fhir_meta, parse_reference, to_uuid
from app.services.mapping.resources.base import BaseMapper
from app.services.provenance import ProvenanceService
from app.services.terminology import TerminologyService


_UNIT_RE = re.compile(r"^[A-Za-z/%][A-Za-z0-9/%]*$")


def _parse_dt(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _category_from_fhir(body: dict[str, Any]) -> str | None:
    for cat in body.get("category") or []:
        for coding in cat.get("coding") or []:
            if coding.get("code") in ("laboratory", "lab"):
                return "lab"
            if coding.get("code") in ("vital-signs", "vital"):
                return "vital"
    return None


class ObservationMapper(BaseMapper):
    resource_type = "Observation"

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

        encounter_id = None
        if body.get("encounter", {}).get("reference"):
            rt, rid = parse_reference(body["encounter"]["reference"])
            if rt != "Encounter":
                raise ValueError("Observation.encounter must reference Encounter")
            encounter_id = to_uuid(rid)
            enc = self.db.get(SomEncounter, encounter_id)
            if not enc:
                raise ValueError("Encounter not found")
            if enc.patient_id != patient.id:
                raise ValueError("Encounter.patient must match Observation.patient")

        status = body.get("status")
        if not status:
            raise ValueError("Observation.status required")

        effective = body.get("effectiveDateTime")
        if not effective:
            raise ValueError("Observation.effectiveDateTime required")
        effective_dt = _parse_dt(effective)

        code_cc = body.get("code") or {}
        coding = TerminologyService.pick_coding(code_cc)
        code_concept = TerminologyService(self.db).normalize_concept(
            system=coding["system"],
            code=coding["code"],
            display=coding.get("display"),
            version=coding.get("version"),
            correlation_id=correlation_id,
        )

        value_type = None
        vq_value = None
        vq_unit = None
        vc_id = None

        if "valueQuantity" in body:
            vq = body["valueQuantity"]
            if vq.get("unit") is None:
                raise ValueError("Quantity unit required")
            unit = str(vq.get("unit"))
            if unit not in {"%", "mg/dL", "mmol/L", "mmHg", "bpm"} and not _UNIT_RE.match(unit):
                raise ValueError("Quantity unit must match UCUM-like rule")
            value_type = "quantity"
            vq_value = float(vq.get("value")) if vq.get("value") is not None else None
            vq_unit = unit
        elif "valueCodeableConcept" in body:
            cc = body["valueCodeableConcept"]
            c = TerminologyService.pick_coding(cc)
            vc = TerminologyService(self.db).normalize_concept(
                system=c["system"],
                code=c["code"],
                display=c.get("display"),
                version=c.get("version"),
                correlation_id=correlation_id,
            )
            value_type = "codeable_concept"
            vc_id = vc.id

        prov = ProvenanceService(self.db).create(activity="create", author=None, correlation_id=correlation_id)
        obs = SomObservation(
            patient_id=patient.id,
            encounter_id=encounter_id,
            status=status,
            category=_category_from_fhir(body),
            code_concept_id=code_concept.id,
            effective_time=effective_dt,
            value_type=value_type,
            value_quantity_value=vq_value,
            value_quantity_unit=vq_unit,
            value_concept_id=vc_id,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(obs)
        self.db.flush()
        self._write_version(obs, provenance_id=prov.id)
        out = self._to_fhir(obs)
        AuditService(self.db).emit(
            actor="system",
            operation="create",
            correlation_id=correlation_id,
            resource_type=self.resource_type,
            resource_id=obs.id,
            som_table="som_observation",
            som_id=obs.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def read(self, id: str) -> dict[str, Any] | None:
        obs = self.db.get(SomObservation, to_uuid(id))
        return self._to_fhir(obs) if obs else None

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        obs = self.db.get(SomObservation, to_uuid(id))
        if not obs:
            return None

        status = body.get("status") or obs.status
        effective = body.get("effectiveDateTime")
        effective_dt = _parse_dt(effective) if effective else obs.effective_time

        encounter_id = obs.encounter_id
        if body.get("encounter", {}).get("reference"):
            rt, rid = parse_reference(body["encounter"]["reference"])
            if rt != "Encounter":
                raise ValueError("Observation.encounter must reference Encounter")
            encounter_id = to_uuid(rid)
            enc = self.db.get(SomEncounter, encounter_id)
            if not enc:
                raise ValueError("Encounter not found")
            if enc.patient_id != obs.patient_id:
                raise ValueError("Encounter.patient must match Observation.patient")

        code_cc = body.get("code") or {}
        coding = TerminologyService.pick_coding(code_cc)
        code_concept = TerminologyService(self.db).normalize_concept(
            system=coding["system"],
            code=coding["code"],
            display=coding.get("display"),
            version=coding.get("version"),
            correlation_id=correlation_id,
        )

        value_type = None
        vq_value = None
        vq_unit = None
        vc_id = None

        if "valueQuantity" in body:
            vq = body["valueQuantity"]
            if vq.get("unit") is None:
                raise ValueError("Quantity unit required")
            unit = str(vq.get("unit"))
            if unit not in {"%", "mg/dL", "mmol/L", "mmHg", "bpm"} and not _UNIT_RE.match(unit):
                raise ValueError("Quantity unit must match UCUM-like rule")
            value_type = "quantity"
            vq_value = float(vq.get("value")) if vq.get("value") is not None else None
            vq_unit = unit
        elif "valueCodeableConcept" in body:
            cc = body["valueCodeableConcept"]
            c = TerminologyService.pick_coding(cc)
            vc = TerminologyService(self.db).normalize_concept(
                system=c["system"],
                code=c["code"],
                display=c.get("display"),
                version=c.get("version"),
                correlation_id=correlation_id,
            )
            value_type = "codeable_concept"
            vc_id = vc.id

        prov = ProvenanceService(self.db).create(activity="update", author=None, correlation_id=correlation_id)
        obs.status = status
        obs.category = _category_from_fhir(body) or obs.category
        obs.code_concept_id = code_concept.id
        obs.effective_time = effective_dt
        obs.encounter_id = encounter_id
        obs.value_type = value_type
        obs.value_quantity_value = vq_value
        obs.value_quantity_unit = vq_unit
        obs.value_concept_id = vc_id
        obs.version += 1
        obs.updated_provenance_id = prov.id
        obs.extensions = obs.extensions or {}

        self._write_version(obs, provenance_id=prov.id)
        out = self._to_fhir(obs)
        AuditService(self.db).emit(
            actor="system",
            operation="update",
            correlation_id=correlation_id,
            resource_type=self.resource_type,
            resource_id=obs.id,
            som_table="som_observation",
            som_id=obs.id,
            request_payload=body,
            result_payload=out,
        )
        return out

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        stmt = select(SomObservation)
        patient = params.get("patient")
        if patient:
            pid = patient.split("/")[-1]
            stmt = stmt.where(SomObservation.patient_id == to_uuid(pid))

        encounter = params.get("encounter")
        if encounter:
            enc_id = encounter.split("/")[-1]
            stmt = stmt.where(SomObservation.encounter_id == to_uuid(enc_id))

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
            stmt = stmt.where(SomObservation.code_concept_id.in_(sub))

        category = params.get("category")
        if category:
            if category in ("lab", "laboratory"):
                stmt = stmt.where(SomObservation.category == "lab")
            if category in ("vital", "vital-signs"):
                stmt = stmt.where(SomObservation.category == "vital")

        date_param = params.get("date")
        if date_param:
            parts = date_param if isinstance(date_param, list) else [date_param]
            for p in parts:
                if p.startswith("ge"):
                    d = _parse_dt(p[2:])
                    stmt = stmt.where(SomObservation.effective_time >= d)
                if p.startswith("le"):
                    d = _parse_dt(p[2:])
                    stmt = stmt.where(SomObservation.effective_time <= d)

        status = params.get("status")
        if not status:
            stmt = stmt.where(SomObservation.status != "entered-in-error")

        if sort == "-date" or sort == "_lastUpdated" or sort == "-_lastUpdated":
            stmt = stmt.order_by(desc(SomObservation.effective_time))
        else:
            stmt = stmt.order_by(desc(SomObservation.effective_time))

        stmt = stmt.limit(count)
        items = self.db.execute(stmt).scalars().all()
        return bundle(entries=[self._to_fhir(i) for i in items], total=len(items))

    def history(self, id: str) -> dict[str, Any]:
        obs = self.db.get(SomObservation, to_uuid(id))
        if not obs:
            raise ValueError("Not found")
        versions = (
            self.db.execute(
                select(SomObservationVersion)
                .where(SomObservationVersion.observation_id == obs.id)
                .order_by(SomObservationVersion.version.asc())
            )
            .scalars()
            .all()
        )
        entries = [self._to_fhir_from_version(obs=obs, v=v) for v in versions]
        return {
            "resourceType": "Bundle",
            "type": "history",
            "total": len(entries),
            "entry": [{"resource": e} for e in entries],
        }

    def _write_version(self, obs: SomObservation, *, provenance_id) -> None:
        v = SomObservationVersion(
            observation_id=obs.id,
            version=obs.version,
            status=obs.status,
            category=obs.category,
            code_concept_id=obs.code_concept_id,
            effective_time=obs.effective_time,
            value_type=obs.value_type,
            value_quantity_value=obs.value_quantity_value,
            value_quantity_unit=obs.value_quantity_unit,
            value_concept_id=obs.value_concept_id,
            provenance_id=provenance_id,
            extensions=obs.extensions,
        )
        self.db.add(v)

    def _to_fhir(self, o: SomObservation) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(o.id),
            "meta": fhir_meta(version=o.version, last_updated=o.updated_time),
            "status": o.status,
            "subject": {"reference": f"Patient/{o.patient_id}"},
            "effectiveDateTime": o.effective_time.isoformat().replace("+00:00", "Z"),
            "code": {
                "coding": [
                    {
                        "system": o.code_concept.code_system.system_uri,
                        "code": o.code_concept.code,
                        "display": o.code_concept.display,
                    }
                ]
            },
        }
        if o.encounter_id:
            out["encounter"] = {"reference": f"Encounter/{o.encounter_id}"}
        if o.category:
            code = "laboratory" if o.category == "lab" else "vital-signs" if o.category == "vital" else o.category
            out["category"] = [{"coding": [{"code": code}]}]
        if o.value_type == "quantity":
            out["valueQuantity"] = {"value": float(o.value_quantity_value) if o.value_quantity_value is not None else None, "unit": o.value_quantity_unit}
        if o.value_type == "codeable_concept" and o.value_concept:
            out["valueCodeableConcept"] = {
                "coding": [
                    {
                        "system": o.value_concept.code_system.system_uri,
                        "code": o.value_concept.code,
                        "display": o.value_concept.display,
                    }
                ]
            }
        return out

    def _to_fhir_from_version(self, *, obs: SomObservation, v: SomObservationVersion) -> dict[str, Any]:
        code = self.db.get(SomConcept, v.code_concept_id)
        value_concept = self.db.get(SomConcept, v.value_concept_id) if v.value_concept_id else None
        out: dict[str, Any] = {
            "resourceType": self.resource_type,
            "id": str(obs.id),
            "meta": {"versionId": str(v.version), "lastUpdated": v.recorded_time.isoformat().replace("+00:00", "Z")},
            "status": v.status,
            "subject": {"reference": f"Patient/{obs.patient_id}"},
            "effectiveDateTime": v.effective_time.isoformat().replace("+00:00", "Z"),
            "code": {
                "coding": [
                    {
                        "system": code.code_system.system_uri if code else None,
                        "code": code.code if code else None,
                        "display": code.display if code else None,
                    }
                ]
            },
        }
        if v.category:
            out["category"] = [{"coding": [{"code": "laboratory" if v.category == "lab" else "vital-signs" if v.category == "vital" else v.category}]}]
        if v.value_type == "quantity":
            out["valueQuantity"] = {
                "value": float(v.value_quantity_value) if v.value_quantity_value is not None else None,
                "unit": v.value_quantity_unit,
            }
        if v.value_type == "codeable_concept" and value_concept:
            out["valueCodeableConcept"] = {
                "coding": [
                    {
                        "system": value_concept.code_system.system_uri,
                        "code": value_concept.code,
                        "display": value_concept.display,
                    }
                ]
            }
        return out
