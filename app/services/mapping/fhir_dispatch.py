from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.mapping.resources.condition import ConditionMapper
from app.services.mapping.resources.document_reference import DocumentReferenceMapper
from app.services.mapping.resources.encounter import EncounterMapper
from app.services.mapping.resources.observation import ObservationMapper
from app.services.mapping.resources.organization import OrganizationMapper
from app.services.mapping.resources.patient import PatientMapper
from app.services.mapping.resources.practitioner import PractitionerMapper
from app.services.mapping.resources.provenance import ProvenanceMapper
from app.services.mapping.resources.service_request import ServiceRequestMapper
from app.services.mapping.resources.binary import BinaryMapper


def _mapper(db: Session, resource_type: str):
    rt = resource_type.lower()
    if rt == "patient":
        return PatientMapper(db)
    if rt == "encounter":
        return EncounterMapper(db)
    if rt == "observation":
        return ObservationMapper(db)
    if rt == "binary":
        return BinaryMapper(db)
    if rt == "practitioner":
        return PractitionerMapper(db)
    if rt == "organization":
        return OrganizationMapper(db)
    if rt == "condition":
        return ConditionMapper(db)
    if rt == "documentreference":
        return DocumentReferenceMapper(db)
    if rt == "servicerequest":
        return ServiceRequestMapper(db)
    if rt == "provenance":
        return ProvenanceMapper(db)
    raise ValueError(f"Unsupported resource type: {resource_type}")


def fhir_create(db: Session, resource_type: str, body: dict[str, Any], correlation_id: str | None) -> dict[str, Any]:
    return _mapper(db, resource_type).create(body, correlation_id=correlation_id)


def fhir_read(db: Session, resource_type: str, id: str) -> dict[str, Any] | None:
    return _mapper(db, resource_type).read(id)


def fhir_update(
    db: Session, resource_type: str, id: str, body: dict[str, Any], correlation_id: str | None
) -> dict[str, Any] | None:
    return _mapper(db, resource_type).update(id, body, correlation_id=correlation_id)


def fhir_search(db: Session, resource_type: str, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
    return _mapper(db, resource_type).search(params=params, count=count, sort=sort)


def fhir_history(db: Session, resource_type: str, id: str) -> dict[str, Any]:
    return _mapper(db, resource_type).history(id)
