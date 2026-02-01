"""provenance targets and audit links

Revision ID: 0006_provenance_links
Revises: 0005_service_request_encounter
Create Date: 2026-02-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0006_provenance_links"
down_revision = "0005_service_request_encounter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("som_provenance", sa.Column("agent_type", sa.Text(), nullable=True))
    op.add_column("som_provenance", sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("som_provenance", sa.Column("agent_display", sa.Text(), nullable=True))
    op.add_column("som_provenance", sa.Column("agent_organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_som_provenance_agent_org",
        "som_provenance",
        "som_organization",
        ["agent_organization_id"],
        ["id"],
    )
    op.add_column("som_provenance", sa.Column("target_resource_type", sa.Text(), nullable=True))
    op.add_column("som_provenance", sa.Column("target_resource_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("som_provenance", sa.Column("target_som_table", sa.Text(), nullable=True))
    op.add_column("som_provenance", sa.Column("target_som_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.add_column("som_audit_event", sa.Column("provenance_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_som_audit_event_provenance",
        "som_audit_event",
        "som_provenance",
        ["provenance_id"],
        ["id"],
    )

    op.add_column("som_preauth_status_history", sa.Column("provenance_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_som_preauth_status_history_provenance",
        "som_preauth_status_history",
        "som_provenance",
        ["provenance_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_som_preauth_status_history_provenance", "som_preauth_status_history", type_="foreignkey")
    op.drop_column("som_preauth_status_history", "provenance_id")

    op.drop_constraint("fk_som_audit_event_provenance", "som_audit_event", type_="foreignkey")
    op.drop_column("som_audit_event", "provenance_id")

    op.drop_column("som_provenance", "target_som_id")
    op.drop_column("som_provenance", "target_som_table")
    op.drop_column("som_provenance", "target_resource_id")
    op.drop_column("som_provenance", "target_resource_type")

    op.drop_constraint("fk_som_provenance_agent_org", "som_provenance", type_="foreignkey")
    op.drop_column("som_provenance", "agent_organization_id")
    op.drop_column("som_provenance", "agent_display")
    op.drop_column("som_provenance", "agent_id")
    op.drop_column("som_provenance", "agent_type")

