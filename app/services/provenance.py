from __future__ import annotations

import datetime as dt
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
        extensions: dict[str, Any] | None = None,
    ) -> SomProvenance:
        prov = SomProvenance(
            source_system=source_system or settings.default_source_system,
            recorded_time=dt.datetime.now(dt.timezone.utc),
            activity=activity,
            author=author,
            original_record_ref=original_record_ref,
            correlation_id=correlation_id,
            extensions=extensions or {},
        )
        self.db.add(prov)
        self.db.flush()
        return prov

