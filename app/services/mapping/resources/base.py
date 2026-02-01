from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


class BaseMapper:
    resource_type: str

    def __init__(self, db: Session):
        self.db = db

    def create(self, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        raise NotImplementedError

    def read(self, id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def update(self, id: str, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any] | None:
        raise NotImplementedError

    def search(self, *, params: dict[str, Any], count: int, sort: str | None) -> dict[str, Any]:
        raise NotImplementedError

    def history(self, id: str) -> dict[str, Any]:
        raise ValueError("History not supported for this resource")

