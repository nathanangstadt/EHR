from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_service_request_reason"
down_revision = "0003_payer_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "som_service_request_reason",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_request_id", sa.UUID(), nullable=False),
        sa.Column("condition_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["service_request_id"], ["som_service_request.id"]),
        sa.ForeignKeyConstraint(["condition_id"], ["som_condition.id"]),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
        sa.UniqueConstraint("service_request_id", "condition_id", "role", name="uq_sr_reason_unique"),
    )
    op.create_index("ix_sr_reason_sr", "som_service_request_reason", ["service_request_id"], unique=False)
    op.create_index("ix_sr_reason_condition", "som_service_request_reason", ["condition_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sr_reason_condition", table_name="som_service_request_reason")
    op.drop_index("ix_sr_reason_sr", table_name="som_service_request_reason")
    op.drop_table("som_service_request_reason")

