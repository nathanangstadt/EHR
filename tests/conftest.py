import os
import subprocess

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")


def pytest_sessionstart(session):
    # Ensure schema exists for a fresh DB.
    subprocess.check_call(["alembic", "upgrade", "head"])

    # Keep tests deterministic even when re-run against the same DB volume.
    from sqlalchemy import text

    from app.db.session import engine

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname='public'
                  AND tablename <> 'alembic_version'
                """
            )
        ).fetchall()
        tables = [r[0] for r in rows]
        if tables:
            conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE;"))
