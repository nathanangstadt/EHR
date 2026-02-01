from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SomCodeSystem, SomConcept
from app.services.provenance import ProvenanceService


class TerminologyService:
    def __init__(self, db: Session):
        self.db = db

    def normalize_concept(
        self,
        *,
        system: str,
        code: str,
        display: str | None,
        version: str | None,
        correlation_id: str | None,
    ) -> SomConcept:
        prov = ProvenanceService(self.db).create(
            activity="normalize-concept",
            author=None,
            correlation_id=correlation_id,
        )

        cs = self.db.execute(select(SomCodeSystem).where(SomCodeSystem.system_uri == system)).scalar_one_or_none()
        if not cs:
            cs = SomCodeSystem(
                system_uri=system,
                name=None,
                default_version=version,
                created_provenance_id=prov.id,
                updated_provenance_id=None,
                extensions={},
            )
            self.db.add(cs)
            self.db.flush()
        else:
            if version and not cs.default_version:
                cs.default_version = version
                cs.version += 1
                cs.updated_provenance_id = prov.id

        stmt = (
            select(SomConcept)
            .where(SomConcept.code_system_id == cs.id)
            .where(SomConcept.code == code)
            .where(SomConcept.version_string.is_(None) if version is None else SomConcept.version_string == version)
        )
        concept = self.db.execute(stmt).scalar_one_or_none()
        if not concept:
            concept = SomConcept(
                code_system_id=cs.id,
                code=code,
                display=display,
                version_string=version,
                created_provenance_id=prov.id,
                updated_provenance_id=None,
                extensions={},
            )
            self.db.add(concept)
            self.db.flush()
        else:
            if display and not concept.display:
                concept.display = display
                concept.version += 1
                concept.updated_provenance_id = prov.id
        return concept

    @staticmethod
    def pick_coding(codeable_concept: dict[str, Any]) -> dict[str, Any]:
        codings = codeable_concept.get("coding") or []
        for c in codings:
            if c.get("system") and c.get("code"):
                return c
        raise ValueError("Missing coding.system/code")

