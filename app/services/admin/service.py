from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.seed import seed
from app.services.audit import AuditService
from app.services.provenance import ProvenanceService


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    def reset_seed_data(self, *, correlation_id: str | None, seed_data: bool = True) -> dict[str, Any]:
        if settings.app_env != "dev":
            raise ValueError("Reset is only allowed when APP_ENV=dev")

        # Lock so two resets can't run concurrently.
        lock_id = 9_884_221
        self.db.execute(text("select pg_advisory_lock(:id)"), {"id": lock_id})
        try:
            tables = [
                r[0]
                for r in self.db.execute(
                    text(
                        "select tablename from pg_tables where schemaname = 'public' and tablename <> 'alembic_version'"
                    )
                ).all()
            ]
            if not tables:
                raise ValueError("No tables found to reset")

            quoted = ", ".join(f'"{t}"' for t in tables)
            # CASCADE handles FK ordering; audit/provenance/history/etc are all truncated too.
            self.db.execute(text(f"truncate table {quoted} restart identity cascade"))
            self.db.commit()

            seed_result = {"ok": "skipped"}
            if seed_data:
                seed_result = seed(self.db)
                self.db.commit()

            out = {"ok": True, "seeded": bool(seed_data), "seedResult": seed_result}
            prov = ProvenanceService(self.db).create(
                activity="reset",
                author="system",
                correlation_id=correlation_id,
                target_resource_type="AdminReset",
            )
            AuditService(self.db).emit(
                actor="system",
                operation="reset",
                correlation_id=correlation_id,
                provenance_id=prov.id,
                resource_type="AdminReset",
                resource_id=None,
                som_table=None,
                som_id=None,
                request_payload={"seed": seed_data},
                result_payload=out,
            )
            return out
        finally:
            self.db.execute(text("select pg_advisory_unlock(:id)"), {"id": lock_id})
