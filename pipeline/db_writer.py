"""Database writes for pipeline schemas only (sc_raw/sc_analytics)."""

from __future__ import annotations

from typing import List, Optional

import psycopg2
from psycopg2.errors import UndefinedTable
from psycopg2.extras import execute_values


def upsert_sales_traffic(rows: List[dict], db_url: str) -> int:
    if not rows:
        return 0

    values = [
        (
            r["report_date"],
            r["marketplace_id"],
            r["account_id"],
            r["child_asin"],
            r.get("parent_asin"),
            r.get("ordered_revenue"),
            r.get("ordered_revenue_currency"),
            r.get("units_ordered"),
            r.get("total_order_items"),
            r.get("page_views"),
            r.get("sessions"),
            r.get("buy_box_percentage"),
            r.get("unit_session_percentage"),
            r.get("query_id"),
        )
        for r in rows
    ]

    sql = """
        INSERT INTO sc_raw.sales_traffic (
            report_date, marketplace_id, account_id, child_asin, parent_asin,
            ordered_revenue, ordered_revenue_currency,
            units_ordered, total_order_items,
            page_views, sessions, buy_box_percentage,
            unit_session_percentage, query_id
        ) VALUES %s
        ON CONFLICT (report_date, marketplace_id, account_id, child_asin)
        DO UPDATE SET
            parent_asin = EXCLUDED.parent_asin,
            ordered_revenue = EXCLUDED.ordered_revenue,
            ordered_revenue_currency = EXCLUDED.ordered_revenue_currency,
            units_ordered = EXCLUDED.units_ordered,
            total_order_items = EXCLUDED.total_order_items,
            page_views = EXCLUDED.page_views,
            sessions = EXCLUDED.sessions,
            buy_box_percentage = EXCLUDED.buy_box_percentage,
            unit_session_percentage = EXCLUDED.unit_session_percentage,
            pulled_at = NOW(),
            query_id = EXCLUDED.query_id
    """

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
            affected = cur.rowcount
        conn.commit()
    return affected


def log_pipeline_run(
    db_url: str,
    target_date,
    marketplace_id: str,
    account_id: str,
    query_id: Optional[str],
    status: str,
    records: int = 0,
    error: Optional[str] = None,
    duration: int = 0,
) -> None:
    sql = """
        INSERT INTO sc_raw.pipeline_log (
            target_date, marketplace_id, account_id, query_id, status,
            records_written, error_message, duration_secs
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (target_date, marketplace_id, account_id, query_id, status, records, error, duration))
        conn.commit()


def verify_pipeline_tables_exist(db_url: str) -> None:
    """Fail fast if required pipeline tables are missing."""
    check_sql = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'sc_raw' AND table_name = 'pipeline_log'
        )
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(check_sql)
            exists = cur.fetchone()[0]
    if not exists:
        raise RuntimeError(
            "Missing table sc_raw.pipeline_log. Run migrations first: `python3 db/migrate.py`."
        )
