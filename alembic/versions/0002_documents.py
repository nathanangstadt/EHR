from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_documents"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "som_binary",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.Text(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_binary_sha", "som_binary", ["sha256_hex"], unique=False)

    op.create_table(
        "som_document",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("encounter_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("type_concept_id", sa.UUID(), nullable=False),
        sa.Column("date_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("binary_id", sa.UUID(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["patient_id"], ["som_patient.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["som_encounter.id"]),
        sa.ForeignKeyConstraint(["type_concept_id"], ["som_concept.id"]),
        sa.ForeignKeyConstraint(["binary_id"], ["som_binary.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_doc_patient", "som_document", ["patient_id"], unique=False)
    op.create_index("ix_doc_type", "som_document", ["type_concept_id"], unique=False)
    op.create_index("ix_doc_date", "som_document", ["date_time"], unique=False)

    op.create_table(
        "som_preauth_supporting_document",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("preauth_request_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("added_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("provenance_id", sa.UUID(), nullable=False),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["preauth_request_id"], ["som_preauth_request.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["som_document.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["som_provenance.id"]),
        sa.UniqueConstraint("preauth_request_id", "document_id", "role", name="uq_preauth_doc_unique"),
    )
    op.create_index("ix_preauth_doc_preauth", "som_preauth_supporting_document", ["preauth_request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_preauth_doc_preauth", table_name="som_preauth_supporting_document")
    op.drop_table("som_preauth_supporting_document")
    op.drop_index("ix_doc_date", table_name="som_document")
    op.drop_index("ix_doc_type", table_name="som_document")
    op.drop_index("ix_doc_patient", table_name="som_document")
    op.drop_table("som_document")
    op.drop_index("ix_binary_sha", table_name="som_binary")
    op.drop_table("som_binary")

