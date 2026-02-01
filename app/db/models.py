from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class SomBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_provenance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_provenance.id"))
    updated_provenance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("som_provenance.id"), nullable=True
    )
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomProvenance(Base):
    __tablename__ = "som_provenance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(Text)
    recorded_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activity: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_record_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomAuditEvent(Base):
    __tablename__ = "som_audit_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recorded_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(Text, default="system")
    operation: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    som_table: Mapped[str | None] = mapped_column(Text, nullable=True)
    som_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomCodeSystem(SomBase):
    __tablename__ = "som_code_system"

    system_uri: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_version: Mapped[str | None] = mapped_column(Text, nullable=True)


class SomConcept(SomBase):
    __tablename__ = "som_concept"
    __table_args__ = (UniqueConstraint("code_system_id", "code", "version_string", name="uq_concept_system_code_ver"),)

    code_system_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_code_system.id"))
    code: Mapped[str] = mapped_column(Text)
    display: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_string: Mapped[str | None] = mapped_column(Text, nullable=True)

    code_system: Mapped[SomCodeSystem] = relationship()


class SomPatient(SomBase):
    __tablename__ = "som_patient"

    identifier_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    identifier_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_family: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_given: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


class SomPractitioner(SomBase):
    __tablename__ = "som_practitioner"
    name: Mapped[str | None] = mapped_column(Text, nullable=True)


class SomOrganization(SomBase):
    __tablename__ = "som_organization"
    name: Mapped[str | None] = mapped_column(Text, nullable=True)


class SomEncounter(SomBase):
    __tablename__ = "som_encounter"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_patient.id"))
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped[SomPatient] = relationship()


class SomCondition(SomBase):
    __tablename__ = "som_condition"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_patient.id"))
    code_concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"))
    clinical_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    onset_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    patient: Mapped[SomPatient] = relationship()
    code_concept: Mapped[SomConcept] = relationship(foreign_keys=[code_concept_id])


class SomServiceRequest(SomBase):
    __tablename__ = "som_service_request"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_patient.id"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_encounter.id"), nullable=True)
    code_concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"))
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    authored_on: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped[SomPatient] = relationship()
    encounter: Mapped[SomEncounter | None] = relationship()
    code_concept: Mapped[SomConcept] = relationship(foreign_keys=[code_concept_id])


class SomServiceRequestReason(SomBase):
    __tablename__ = "som_service_request_reason"
    __table_args__ = (UniqueConstraint("service_request_id", "condition_id", "role", name="uq_sr_reason_unique"),)

    service_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_service_request.id"))
    condition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_condition.id"))
    role: Mapped[str] = mapped_column(Text, default="reason")
    rank: Mapped[int] = mapped_column(Integer, default=1)

    service_request: Mapped[SomServiceRequest] = relationship()
    condition: Mapped[SomCondition] = relationship()


class SomObservation(SomBase):
    __tablename__ = "som_observation"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_patient.id"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_encounter.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"))
    effective_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    value_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_quantity_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    value_quantity_unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_concept_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"), nullable=True)

    patient: Mapped[SomPatient] = relationship()
    encounter: Mapped[SomEncounter | None] = relationship()
    code_concept: Mapped[SomConcept] = relationship(foreign_keys=[code_concept_id])
    value_concept: Mapped[SomConcept | None] = relationship(foreign_keys=[value_concept_id])


class SomObservationVersion(Base):
    __tablename__ = "som_observation_version"
    __table_args__ = (UniqueConstraint("observation_id", "version", name="uq_obs_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_observation.id"))
    version: Mapped[int] = mapped_column(Integer)
    recorded_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    status: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"))
    effective_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    value_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_quantity_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    value_quantity_unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_concept_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"), nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_provenance.id"))
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomJob(Base):
    __tablename__ = "som_job"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomBinary(SomBase):
    __tablename__ = "som_binary"

    content_type: Mapped[str] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256_hex: Mapped[str] = mapped_column(Text)


class SomDocument(SomBase):
    __tablename__ = "som_document"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_patient.id"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_encounter.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text)
    type_concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_concept.id"))
    date_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    binary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_binary.id"), nullable=True)

    patient: Mapped[SomPatient] = relationship()
    encounter: Mapped[SomEncounter | None] = relationship()
    type_concept: Mapped[SomConcept] = relationship(foreign_keys=[type_concept_id])
    binary: Mapped[SomBinary | None] = relationship()


class SomPreAuthSupportingDocument(Base):
    __tablename__ = "som_preauth_supporting_document"
    __table_args__ = (UniqueConstraint("preauth_request_id", "document_id", "role", name="uq_preauth_doc_unique"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preauth_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_preauth_request.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_document.id"))
    role: Mapped[str] = mapped_column(Text)
    added_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_provenance.id"))
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomPayerRuleSet(SomBase):
    __tablename__ = "som_payer_rule_set"

    payer: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # draft | active | archived
    schema_version: Mapped[str] = mapped_column(Text, default="1")
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SomPreAuthRequest(SomBase):
    __tablename__ = "som_preauth_request"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_patient.id"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_encounter.id"), nullable=True)
    practitioner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_practitioner.id"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("som_organization.id"), nullable=True)
    diagnosis_condition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_condition.id"))
    service_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_service_request.id"))
    status: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(Text)
    payer: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[SomPatient] = relationship()
    encounter: Mapped[SomEncounter | None] = relationship()
    practitioner: Mapped[SomPractitioner] = relationship()
    organization: Mapped[SomOrganization | None] = relationship()
    diagnosis_condition: Mapped[SomCondition] = relationship()
    service_request: Mapped[SomServiceRequest] = relationship()


class SomPreAuthPackageSnapshot(Base):
    __tablename__ = "som_preauth_package_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preauth_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_preauth_request.id"))
    created_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_provenance.id"))
    schema_version: Mapped[str] = mapped_column(Text, default="1")
    checksum: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomPreAuthDecision(Base):
    __tablename__ = "som_preauth_decision"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preauth_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_preauth_request.id"))
    decided_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    outcome: Mapped[str] = mapped_column(Text)
    reason_codes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_additional_info: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    raw_payer_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_provenance.id"))
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SomPreAuthStatusHistory(Base):
    __tablename__ = "som_preauth_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preauth_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("som_preauth_request.id"))
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text)
    changed_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    changed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    extensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


def db_now():
    return func.now()
