from __future__ import annotations

import os
import subprocess

from app.core.config import settings


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def main() -> None:
    from app.scripts.wait_for_db import main as wait

    wait()
    if settings.auto_migrate:
        _run(["alembic", "upgrade", "head"])
    if settings.auto_seed:
        _run(["python", "-m", "app.seed"])


if __name__ == "__main__":
    main()

