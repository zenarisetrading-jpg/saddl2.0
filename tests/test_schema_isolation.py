"""Schema isolation tests for diagnostic Phase 1 artifacts."""

from __future__ import annotations

import re
from pathlib import Path


FORBIDDEN_WRITE_PATTERNS = [
    r"INSERT\s+INTO\s+public\.",
    r"UPDATE\s+public\.",
    r"DELETE\s+FROM\s+public\.",
    r"ALTER\s+TABLE\s+public\.",
    r"CREATE\s+TABLE\s+public\.",
    r"CREATE\s+VIEW\s+public\.",
    r"DROP\s+TABLE\s+public\.",
    r"DROP\s+VIEW\s+public\.",
]


def _assert_no_forbidden_writes(text: str, source: str) -> None:
    for pattern in FORBIDDEN_WRITE_PATTERNS:
        assert not re.search(pattern, text, flags=re.IGNORECASE), (
            f"Forbidden write pattern '{pattern}' found in {source}"
        )


def test_no_public_schema_references_in_sql():
    sql_files = list(Path("db/migrations").glob("003_*.sql"))
    assert sql_files, "Expected at least one Phase 1 migration file (003_*.sql)"
    for path in sql_files:
        _assert_no_forbidden_writes(path.read_text(), str(path))


def test_no_impact_dashboard_writes():
    bsr_file = Path("pipeline/bsr_pipeline.py")
    assert bsr_file.exists(), "Expected pipeline/bsr_pipeline.py to exist"
    text = bsr_file.read_text()
    forbidden = [
        r"INSERT\s+INTO\s+public\.actions_log",
        r"UPDATE\s+public\.actions_log",
        r"DELETE\s+FROM\s+public\.actions_log",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, text, flags=re.IGNORECASE), (
            f"Forbidden Impact Dashboard write pattern '{pattern}' found in {bsr_file}"
        )


def test_all_new_tables_in_correct_schema():
    migration = Path("db/migrations/003_add_bsr_history.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS sc_raw.bsr_history" in migration
    assert "CREATE OR REPLACE VIEW sc_analytics.bsr_trends AS" in migration
    assert "CREATE TABLE IF NOT EXISTS public." not in migration
    assert "CREATE VIEW public." not in migration


def test_views_only_read_from_allowed_schemas():
    migration = Path("db/migrations/003_add_bsr_history.sql").read_text()
    # Phase 1 bsr_trends view should read only from sc_raw.bsr_history.
    assert "FROM sc_raw.bsr_history" in migration
    view_section = migration.split("CREATE OR REPLACE VIEW sc_analytics.bsr_trends AS", 1)[-1]
    view_sql = view_section.split("INSERT INTO sc_analytics.schema_version", 1)[0]
    assert "INSERT INTO" not in view_sql
    assert "UPDATE " not in view_sql
    assert "DELETE " not in view_sql
