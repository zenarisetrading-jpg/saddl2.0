"""
STR Prorate Migration Script
=============================
Flushes raw_search_term_data for a client over the Excel's date range,
then re-ingests with the new prorating logic (multi-day rows split into daily rows).

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
    parser.add_argument("--file", required=True, help="Path to Excel STR file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    args = parser.parse_args()

    db_url = load_db_url()

    # Load Excel
    print(f"\nLoading: {args.file}")
    df = pd.read_excel(args.file)
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    df['End Date'] = pd.to_datetime(df['End Date'])

    min_date = df['Start Date'].min().date()
    max_date = df['End Date'].max().date()
    total_spend = df['Spend'].sum()
    total_rows = len(df)

    print(f"Excel: {total_rows} rows | {min_date} → {max_date} | Spend: {total_spend:.2f}")

    # Check current DB state
    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(spend)::numeric, 2), MIN(report_date), MAX(report_date)
        FROM raw_search_term_data
        WHERE client_id = %s AND report_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    row = cur.fetchone()
    print(f"\nDB before: {row[2]} → {row[3]} | {row[0]} rows | Spend: {row[1]}")

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

    # Delete
    cur.execute("""
        DELETE FROM raw_search_term_data
        WHERE client_id = %s AND report_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    deleted = cur.rowcount
    conn.commit()
    print(f"Deleted {deleted} rows.")
    cur.close()
    conn.close()

    # Re-ingest with new prorating logic
    print("Re-ingesting with prorating logic...")
    db = PostgresManager(db_url)
    saved = db.save_raw_search_term_data(df, args.client)
    print(f"Saved {saved} rows.")

    # Verify
    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(spend)::numeric, 2), MIN(report_date), MAX(report_date)
        FROM raw_search_term_data
        WHERE client_id = %s AND report_date BETWEEN %s AND %s
    """, (args.client, min_date, max_date))
    row = cur.fetchone()
    print(f"\nDB after:  {row[2]} → {row[3]} | {row[0]} rows | Spend: {row[1]}")
    print(f"Excel total:                                    Spend: {total_spend:.2f}")
    diff = float(row[1] or 0) - total_spend
    print(f"Difference: {diff:.2f} (should be ~0.00)")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
