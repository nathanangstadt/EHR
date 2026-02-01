from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from app.db.models import SomPayerRuleSet
from app.services.audit import AuditService
from app.services.provenance import ProvenanceService


class PayerRuleService:
    def __init__(self, db: Session):
        self.db = db

    def get_active(self, *, payer: str) -> SomPayerRuleSet | None:
        stmt = (
            select(SomPayerRuleSet)
            .where(SomPayerRuleSet.payer == payer)
            .where(SomPayerRuleSet.status == "active")
            .order_by(desc(SomPayerRuleSet.updated_time))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, *, payer: str | None = None) -> list[SomPayerRuleSet]:
        stmt = select(SomPayerRuleSet).order_by(desc(SomPayerRuleSet.updated_time)).limit(200)
        if payer:
            stmt = stmt.where(SomPayerRuleSet.payer == payer)
        return self.db.execute(stmt).scalars().all()

    def upsert_active(
        self,
        *,
        payer: str,
        rules: dict[str, Any],
        notes: str | None,
        correlation_id: str | None,
    ) -> SomPayerRuleSet:
        prov = ProvenanceService(self.db).create(activity="update-payer-rules", author="payer-admin", correlation_id=correlation_id)

        # Archive existing active rules for payer.
        self.db.execute(
            update(SomPayerRuleSet)
            .where(SomPayerRuleSet.payer == payer)
            .where(SomPayerRuleSet.status == "active")
            .values(status="archived", updated_time=dt.datetime.now(dt.timezone.utc), updated_provenance_id=prov.id)
        )

        rs = SomPayerRuleSet(
            payer=payer,
            status="active",
            schema_version=str(rules.get("schemaVersion") or "1"),
            rules=rules,
            notes=notes,
            created_provenance_id=prov.id,
            updated_provenance_id=None,
            extensions={},
        )
        self.db.add(rs)
        self.db.flush()
        ProvenanceService(self.db).set_target(
            prov,
            target_resource_type="PayerRuleSet",
            target_resource_id=str(rs.id),
            target_som_table="som_payer_rule_set",
            target_som_id=str(rs.id),
        )
        AuditService(self.db).emit(
            actor="payer-admin",
            operation="update",
            correlation_id=correlation_id,
            provenance_id=prov.id,
            resource_type="PayerRuleSet",
            resource_id=rs.id,
            som_table="som_payer_rule_set",
            som_id=rs.id,
            request_payload={"payer": payer, "notes": notes},
            result_payload={"id": str(rs.id), "payer": payer, "status": rs.status},
        )
        return rs

    @staticmethod
    def to_dict(rs: SomPayerRuleSet) -> dict[str, Any]:
        return {
            "id": str(rs.id),
            "payer": rs.payer,
            "status": rs.status,
            "schemaVersion": rs.schema_version,
            "rules": rs.rules,
            "notes": rs.notes,
            "version": rs.version,
            "updatedTime": rs.updated_time.isoformat(),
        }
