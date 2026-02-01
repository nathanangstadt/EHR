from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_service_request_encounter"
down_revision = "0004_service_request_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("som_service_request", sa.Column("encounter_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_sr_encounter",
        "som_service_request",
        "som_encounter",
        ["encounter_id"],
        ["id"],
    )
    op.create_index("ix_sr_encounter", "som_service_request", ["encounter_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sr_encounter", table_name="som_service_request")
    op.drop_constraint("fk_sr_encounter", "som_service_request", type_="foreignkey")
    op.drop_column("som_service_request", "encounter_id")

