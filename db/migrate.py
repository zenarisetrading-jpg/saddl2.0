"""Schema migration runner for isolated SP-API pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


load_dotenv()

MIGRATIONS = [
    ("001_create_sc_raw.sql", "Create sc_raw schema and tables"),
    ("002_create_sc_analytics.sql", "Create sc_analytics schema and tables"),
    ("003_add_bsr_history.sql", "Add BSR raw table + trends view"),
    ("005_account_scoping.sql", "Add account scoping + mapping table"),
    ("004_signal_views.sql", "Create account-scoped signal views"),
    ("006_refresh_signal_views_with_mapping.sql", "Compatibility refresh for mapping-aware signal views"),
]


def _get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("Missing required env var: DATABASE_URL")
    return db_url


def run_migrations() -> None:
    db_url = _get_db_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        for filename, description in MIGRATIONS:
            path = Path(__file__).parent / "migrations" / filename
            print(f"Running: {filename}")
            cur.execute(path.read_text())
            conn.commit()
            print(f"  OK {description}")
    finally:
        cur.close()
        conn.close()

    print("\nAll migrations complete.")


def rollback() -> None:
    confirm = input("Type CONFIRM to rollback all pipeline schemas: ")
    if confirm != "CONFIRM":
        print("Aborted.")
        return

    db_url = _get_db_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        path = Path(__file__).parent / "migrations" / "999_rollback_all.sql"
        cur.execute(path.read_text())
        conn.commit()
    finally:
        cur.close()
        conn.close()

    print("Rollback complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        run_migrations()
