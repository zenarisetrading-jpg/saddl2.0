"""Aggregator tests with SQL-call verification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pipeline.aggregator import upsert_account_daily, upsert_osi_index


def test_upsert_account_daily_executes_sql():
    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.__enter__.return_value = fake_conn
    fake_cursor.__enter__.return_value = fake_cursor
    fake_conn.cursor.return_value = fake_cursor

    with patch("pipeline.aggregator.psycopg2.connect", return_value=fake_conn):
        upsert_account_daily(
            "postgresql://example",
            "2026-02-15",
            "A2VIGQ35RCS4UG",
            "s2c_uae_test",
            "s2c_uae_test",
        )

    assert fake_cursor.execute.called


def test_upsert_osi_index_executes_sql():
    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.__enter__.return_value = fake_conn
    fake_cursor.__enter__.return_value = fake_cursor
    fake_conn.cursor.return_value = fake_cursor

    with patch("pipeline.aggregator.psycopg2.connect", return_value=fake_conn):
        upsert_osi_index("postgresql://example", "2026-02-15", "A2VIGQ35RCS4UG", "s2c_uae_test")

    assert fake_cursor.execute.called
