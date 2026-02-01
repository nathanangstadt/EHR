from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_payer_rules"
down_revision = "0002_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "som_payer_rule_set",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("payer", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),  # draft | active | archived
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("rules", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_provenance_id", sa.UUID(), nullable=False),
        sa.Column("updated_provenance_id", sa.UUID(), nullable=True),
        sa.Column("extensions", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["created_provenance_id"], ["som_provenance.id"]),
        sa.ForeignKeyConstraint(["updated_provenance_id"], ["som_provenance.id"]),
    )
    op.create_index("ix_payer_ruleset_payer", "som_payer_rule_set", ["payer"], unique=False)
    op.create_index("ix_payer_ruleset_status", "som_payer_rule_set", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payer_ruleset_status", table_name="som_payer_rule_set")
    op.drop_index("ix_payer_ruleset_payer", table_name="som_payer_rule_set")
    op.drop_table("som_payer_rule_set")

