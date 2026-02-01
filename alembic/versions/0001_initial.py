from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "som_provenance",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("recorded_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activity", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("original_record_ref", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True, index=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "som_audit_event",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recorded_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("som_table", sa.Text(), nullable=True),
        sa.Column("som_id", sa.UUID(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("request_payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "ix_audit_idempotency",
        "som_audit_event",
        ["correlation_id", "operation", "resource_type"],
        unique=False,
    )

    op.create_table(
        "som_code_system",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("system_uri", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("default_version", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )

    op.create_table(
        "som_concept",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code_system_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display", sa.Text(), nullable=True),
        sa.Column("version_string", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["code_system_id"], ["som_code_system.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
        sa.UniqueConstraint("code_system_id", "code", "version_string", name="uq_concept_system_code_ver"),
    )

    op.create_table(
        "som_patient",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("identifier_system", sa.Text(), nullable=True),
        sa.Column("identifier_value", sa.Text(), nullable=True),
        sa.Column("name_family", sa.Text(), nullable=True),
        sa.Column("name_given", sa.Text(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_patient_identifier", "som_patient", ["identifier_system", "identifier_value"], unique=False)
    op.create_index("ix_patient_name", "som_patient", ["name_family", "name_given"], unique=False)

    op.create_table(
        "som_practitioner",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )

    op.create_table(
        "som_organization",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )

    op.create_table(
        "som_encounter",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["patient_id"], ["som_patient.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_encounter_patient", "som_encounter", ["patient_id"], unique=False)

    op.create_table(
        "som_condition",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("code_concept_id", sa.UUID(), nullable=False),
        sa.Column("clinical_status", sa.Text(), nullable=True),
        sa.Column("onset_date", sa.Date(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["patient_id"], ["som_patient.id"]),
        sa.ForeignKeyConstraint(["code_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_condition_patient", "som_condition", ["patient_id"], unique=False)
    op.create_index("ix_condition_code", "som_condition", ["code_concept_id"], unique=False)

    op.create_table(
        "som_service_request",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("code_concept_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("authored_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["patient_id"], ["som_patient.id"]),
        sa.ForeignKeyConstraint(["code_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_sr_patient", "som_service_request", ["patient_id"], unique=False)
    op.create_index("ix_sr_code", "som_service_request", ["code_concept_id"], unique=False)

    op.create_table(
        "som_observation",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("encounter_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("code_concept_id", sa.UUID(), nullable=False),
        sa.Column("effective_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_type", sa.Text(), nullable=True),
        sa.Column("value_quantity_value", sa.Numeric(), nullable=True),
        sa.Column("value_quantity_unit", sa.Text(), nullable=True),
        sa.Column("value_concept_id", sa.UUID(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["patient_id"], ["som_patient.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["som_encounter.id"]),
        sa.ForeignKeyConstraint(["code_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["value_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_obs_patient", "som_observation", ["patient_id"], unique=False)
    op.create_index("ix_obs_code", "som_observation", ["code_concept_id"], unique=False)
    op.create_index("ix_obs_effective", "som_observation", ["effective_time"], unique=False)

    op.create_table(
        "som_observation_version",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recorded_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("code_concept_id", sa.UUID(), nullable=False),
        sa.Column("effective_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_type", sa.Text(), nullable=True),
        sa.Column("value_quantity_value", sa.Numeric(), nullable=True),
        sa.Column("value_quantity_unit", sa.Text(), nullable=True),
        sa.Column("value_concept_id", sa.UUID(), nullable=True),
        sa.Column("provenance_id", sa.UUID(), nullable=False),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["observation_id"], ["som_observation.id"]),
        sa.ForeignKeyConstraint(["code_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["value_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["som_provenance.id"]),
        sa.UniqueConstraint("observation_id", "version", name="uq_obs_version"),
    )

    op.create_table(
        "som_job",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("parameters", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("outputs", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_job_status", "som_job", ["status"], unique=False)
    op.create_index("ix_job_correlation", "som_job", ["correlation_id"], unique=False)

    op.create_table(
        "som_preauth_request",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("encounter_id", sa.UUID(), nullable=True),
        sa.Column("practitioner_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("diagnosis_condition_id", sa.UUID(), nullable=False),
        sa.Column("service_request_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("payer", sa.Text(), nullable=True),
        sa.Column("policy_id", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["patient_id"], ["som_patient.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["som_encounter.id"]),
        sa.ForeignKeyConstraint(["practitioner_id"], ["som_practitioner.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["som_organization.id"]),
        sa.ForeignKeyConstraint(["diagnosis_condition_id"], ["som_condition.id"]),
        sa.ForeignKeyConstraint(["service_request_id"], ["som_service_request.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_preauth_patient", "som_preauth_request", ["patient_id"], unique=False)
    op.create_index("ix_preauth_status", "som_preauth_request", ["status"], unique=False)

    op.create_table(
        "som_preauth_package_snapshot",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("preauth_request_id", sa.UUID(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("provenance_id", sa.UUID(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("checksum", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["preauth_request_id"], ["som_preauth_request.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_snapshot_preauth", "som_preauth_package_snapshot", ["preauth_request_id"], unique=False)

    op.create_table(
        "som_preauth_decision",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("preauth_request_id", sa.UUID(), nullable=False),
        sa.Column("decided_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("reason_codes", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("requested_additional_info", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw_payer_response", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provenance_id", sa.UUID(), nullable=False),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["preauth_request_id"], ["som_preauth_request.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_decision_preauth", "som_preauth_decision", ["preauth_request_id"], unique=False)

    op.create_table(
        "som_preauth_status_history",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("preauth_request_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["preauth_request_id"], ["som_preauth_request.id"]),
    )
    op.create_index("ix_preauth_history_preauth", "som_preauth_status_history", ["preauth_request_id"], unique=False)


def downgrade() -> None:
    op.drop_table("som_preauth_status_history")
    op.drop_table("som_preauth_decision")
    op.drop_table("som_preauth_package_snapshot")
    op.drop_table("som_preauth_request")
    op.drop_index("ix_job_correlation", table_name="som_job")
    op.drop_index("ix_job_status", table_name="som_job")
    op.drop_table("som_job")
    op.drop_table("som_observation_version")
    op.drop_index("ix_obs_effective", table_name="som_observation")
    op.drop_index("ix_obs_code", table_name="som_observation")
    op.drop_index("ix_obs_patient", table_name="som_observation")
    op.drop_table("som_observation")
    op.drop_index("ix_sr_code", table_name="som_service_request")
    op.drop_index("ix_sr_patient", table_name="som_service_request")
    op.drop_table("som_service_request")
    op.drop_index("ix_condition_code", table_name="som_condition")
    op.drop_index("ix_condition_patient", table_name="som_condition")
    op.drop_table("som_condition")
    op.drop_index("ix_encounter_patient", table_name="som_encounter")
    op.drop_table("som_encounter")
    op.drop_table("som_organization")
    op.drop_table("som_practitioner")
    op.drop_index("ix_patient_name", table_name="som_patient")
    op.drop_index("ix_patient_identifier", table_name="som_patient")
    op.drop_table("som_patient")
    op.drop_table("som_concept")
    op.drop_table("som_code_system")
    op.drop_index("ix_audit_idempotency", table_name="som_audit_event")
    op.drop_table("som_audit_event")
    op.drop_table("som_provenance")

