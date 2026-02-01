from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_fixed

from app.db.session import engine


@retry(stop=stop_after_attempt(30), wait=wait_fixed(1))
def main() -> None:
    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")


if __name__ == "__main__":
    main()

