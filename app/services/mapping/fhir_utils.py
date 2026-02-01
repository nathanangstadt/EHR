from __future__ import annotations

import datetime as dt
import uuid
from typing import Any


def fhir_meta(*, version: int, last_updated: dt.datetime) -> dict[str, Any]:
    lu = last_updated
    if lu.tzinfo is None:
        lu = lu.replace(tzinfo=dt.timezone.utc)
    return {"versionId": str(version), "lastUpdated": lu.isoformat().replace("+00:00", "Z")}


def parse_reference(ref: str) -> tuple[str, str]:
    parts = ref.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid reference: {ref}")
    return parts[0], parts[1]


def to_uuid(id_: str) -> uuid.UUID:
    try:
        return uuid.UUID(id_)
    except ValueError:
        raise ValueError("Invalid id (expected UUID)")


def bundle(*, entries: list[dict[str, Any]], total: int) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": total,
        "entry": [{"resource": e} for e in entries],
    }

