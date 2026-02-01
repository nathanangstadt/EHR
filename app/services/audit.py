from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SomAuditEvent


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def emit(
        self,
        *,
        actor: str,
        operation: str,
        correlation_id: str | None,
        resource_type: str | None,
        resource_id: uuid.UUID | None,
        som_table: str | None,
        som_id: uuid.UUID | None,
        request_payload: dict[str, Any] | None = None,
        result_payload: dict[str, Any] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> SomAuditEvent:
        ev = SomAuditEvent(
            recorded_time=dt.datetime.now(dt.timezone.utc),
            actor=actor,
            operation=operation,
            correlation_id=correlation_id,
            resource_type=resource_type,
            resource_id=resource_id,
            som_table=som_table,
            som_id=som_id,
            request_payload=request_payload,
            result_payload=result_payload,
            extensions=extensions or {},
        )
        self.db.add(ev)
        self.db.flush()
        return ev

    def find_idempotent_result(
        self,
        *,
        correlation_id: str,
        operation: str,
        resource_type: str,
        request_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        stmt = (
            select(SomAuditEvent)
            .where(SomAuditEvent.correlation_id == correlation_id)
            .where(SomAuditEvent.operation == operation)
            .where(SomAuditEvent.resource_type == resource_type)
        )
        if request_payload is not None:
            stmt = stmt.where(SomAuditEvent.request_payload == request_payload)
        stmt = stmt.order_by(SomAuditEvent.recorded_time.desc()).limit(1)
        ev = self.db.execute(stmt).scalar_one_or_none()
        return ev.result_payload if ev else None

    def trace(
        self,
        *,
        correlation_id: str | None,
        resource_type: str | None,
        resource_id: str | None,
    ) -> dict[str, Any]:
        stmt = select(SomAuditEvent).order_by(SomAuditEvent.recorded_time.desc()).limit(200)
        if correlation_id:
            stmt = stmt.where(SomAuditEvent.correlation_id == correlation_id)
        if resource_type:
            stmt = stmt.where(SomAuditEvent.resource_type == resource_type)
        if resource_id:
            try:
                rid = uuid.UUID(resource_id)
            except ValueError:
                rid = None
            if rid:
                stmt = stmt.where(SomAuditEvent.resource_id == rid)
        events = self.db.execute(stmt).scalars().all()
        return {
            "events": [
                {
                    "id": str(e.id),
                    "recordedTime": e.recorded_time.isoformat(),
                    "actor": e.actor,
                    "operation": e.operation,
                    "resourceType": e.resource_type,
                    "resourceId": str(e.resource_id) if e.resource_id else None,
                    "somTable": e.som_table,
                    "somId": str(e.som_id) if e.som_id else None,
                    "correlationId": e.correlation_id,
                    "requestPayload": e.request_payload,
                    "resultPayload": e.result_payload,
                }
                for e in events
            ]
        }
