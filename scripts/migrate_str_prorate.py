"""
STR Re-ingest Script
=====================
Flushes raw_search_term_data for a client over the file's date range,
then re-ingests from a daily-granularity STR export (Time Unit = Daily).

Use this to fix data that was previously uploaded with the old proration logic
or from a date-range export.  The replacement file must use daily granularity.

Usage:
    python scripts/migrate_str_prorate.py --client tbs --file "/path/to/file.xlsx" [--dry-run]
"""

import argparse
import os
import sys
import pandas as pd
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_core.postgres_manager import PostgresManager  # noqa: E402


def load_db_url():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith("DATABASE_URL"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("DATABASE_URL not found in .env")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="client_id in DB e.g. tbs")
    parser.add_argument("--file", required=True, help="Path to daily-granularity STR Excel file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    args = parser.parse_args()

    db_url = load_db_url()

    # Load file
    print(f"\nLoading: {args.file}")
    df = pd.read_excel(args.file)

    # Detect date column — daily exports use 'Date'
    date_col = next((c for c in ['Date', 'Start Date', 'date'] if c in df.columns), None)
    if date_col is None:
        print("ERROR: No date column found. Expected 'Date' from a daily-granularity export.")
        return

    if 'End Date' in df.columns or 'end_date' in df.columns:
        print("WARNING: 'End Date' column detected — this looks like a date-range export, not daily.")
        print("         Re-export from Campaign Manager with Time Unit = Daily and retry.")

    df[date_col] = pd.to_datetime(df[date_col])
    min_date = df[date_col].min().date()
    max_date = df[date_col].max().date()
    total_spend = df['Spend'].sum() if 'Spend' in df.columns else 0
    total_rows = len(df)

    print(f"File:  {total_rows} rows | {min_date} → {max_date} | Spend: {total_spend:.2f}")

    # Check current DB state
    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(spend)::numeric, 2), MIN(report_date), MAX(report_date)
        FROM raw_search_term_data
        WHERE client_id = %s AND report_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    row = cur.fetchone()
    print(f"DB before: {row[2]} → {row[3]} | {row[0]} rows | Spend: {row[1]}")

    if args.dry_run:
        print("\n[DRY RUN] Would delete and re-ingest. No changes made.")
        cur.close()
        conn.close()
        return

    # Confirm
    confirm = input(f"\nDelete {row[0]} rows for '{args.client}' ({min_date}→{max_date}) and re-ingest? [yes/no]: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        cur.close()
        conn.close()
        return

    # Delete existing rows for the date range
    cur.execute("""
        DELETE FROM raw_search_term_data
        WHERE client_id = %s AND report_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    deleted = cur.rowcount
    conn.commit()
    print(f"Deleted {deleted} rows.")
    cur.close()
    conn.close()

    # Re-ingest as daily data (no proration)
    print("Re-ingesting as daily data...")
    db = PostgresManager(db_url)
    saved = db.save_raw_search_term_data(df, args.client)
    print(f"Saved {saved} rows.")

    # Rebuild target_stats from the clean raw data
    # First delete existing target_stats rows for this client in the affected date range
    conn2 = psycopg2.connect(db_url, connect_timeout=15)
    cur2 = conn2.cursor()
    cur2.execute("""
        DELETE FROM target_stats
        WHERE client_id = %s AND start_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    ts_deleted = cur2.rowcount
    conn2.commit()
    cur2.close()
    conn2.close()
    print(f"Cleared {ts_deleted} stale rows from target_stats.")

    print("Reaggregating target_stats from clean raw data...")
    agg_count = db.reaggregate_target_stats(args.client)
    print(f"Reaggregated {agg_count} rows into target_stats.")

    # Verify totals match
    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(spend)::numeric, 2), MIN(report_date), MAX(report_date)
        FROM raw_search_term_data
        WHERE client_id = %s AND report_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    row = cur.fetchone()
    print(f"DB after:  {row[2]} → {row[3]} | {row[0]} rows | Spend: {row[1]}")
    print(f"File total:                                     Spend: {total_spend:.2f}")
    diff = float(row[1] or 0) - total_spend
    print(f"Difference: {diff:.2f} (should be ~0.00)")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
