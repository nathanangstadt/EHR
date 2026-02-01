from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import SomProvenance


class ProvenanceService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        activity: str,
        author: str | None,
        correlation_id: str | None,
        original_record_ref: str | None = None,
        source_system: str | None = None,
        agent_type: str | None = None,
        agent_id: str | None = None,
        agent_display: str | None = None,
        agent_organization_id: str | None = None,
        target_resource_type: str | None = None,
        target_resource_id: str | None = None,
        target_som_table: str | None = None,
        target_som_id: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> SomProvenance:
        def _uuid(v: str | None) -> uuid.UUID | None:
            if not v:
                return None
            return uuid.UUID(str(v))

        prov = SomProvenance(
            source_system=source_system or settings.default_source_system,
            recorded_time=dt.datetime.now(dt.timezone.utc),
            activity=activity,
            author=author,
            agent_type=agent_type,
            agent_id=_uuid(agent_id),
            agent_display=agent_display,
            agent_organization_id=_uuid(agent_organization_id),
            original_record_ref=original_record_ref,
            correlation_id=correlation_id,
            target_resource_type=target_resource_type,
            target_resource_id=_uuid(target_resource_id),
            target_som_table=target_som_table,
            target_som_id=_uuid(target_som_id),
            extensions=extensions or {},
        )
        self.db.add(prov)
        self.db.flush()
        return prov

    def set_target(
        self,
        prov: SomProvenance,
        *,
        target_resource_type: str | None,
        target_resource_id: str | None,
        target_som_table: str | None,
        target_som_id: str | None,
    ) -> SomProvenance:
        prov.target_resource_type = target_resource_type
        prov.target_resource_id = uuid.UUID(str(target_resource_id)) if target_resource_id else None
        prov.target_som_table = target_som_table
        prov.target_som_id = uuid.UUID(str(target_som_id)) if target_som_id else None
        self.db.add(prov)
        self.db.flush()
        return prov
