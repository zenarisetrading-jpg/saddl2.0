"""
Delete Pre-February STR Data
=============================
Deletes all raw_search_term_data outside of February 2026 for specified clients.
Leaves Feb 2026 data (2026-02-01 → 2026-02-28) untouched.

Usage:
    python scripts/delete_pre_feb_str.py [--dry-run]
"""

import argparse
import os
import sys
import psycopg2

KEEP_FROM = "2026-02-01"
KEEP_TO   = "2026-02-28"
CLIENTS   = ["tbs", "repro_books_uae", "arya_vastu_20"]


def load_db_url():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith("DATABASE_URL"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("DATABASE_URL not found in .env")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    args = parser.parse_args()

    db_url = load_db_url()
    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()

    print(f"\nKeeping:  {KEEP_FROM} → {KEEP_TO}")
    print(f"Deleting: everything outside that window for {CLIENTS}\n")

    total_rows = 0
    for client in CLIENTS:
        cur.execute("""
            SELECT MIN(report_date), MAX(report_date), COUNT(*), ROUND(SUM(spend)::numeric, 2)
            FROM raw_search_term_data
            WHERE client_id = %s
              AND (report_date < %s OR report_date > %s)
        """, (client, KEEP_FROM, KEEP_TO))
        row = cur.fetchone()
        count = row[2] or 0
        total_rows += count
        print(f"  {client}: {row[0]} → {row[1]} | {count:,} rows | spend: {row[3]}")

    print(f"\nTotal rows to delete: {total_rows:,}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        cur.close()
        conn.close()
        return

    confirm = input(f"\nPermanently delete {total_rows:,} rows for all 3 clients? [yes/no]: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        cur.close()
        conn.close()
        return

    for client in CLIENTS:
        cur.execute("""
            DELETE FROM raw_search_term_data
            WHERE client_id = %s
              AND (report_date < %s OR report_date > %s)
        """, (client, KEEP_FROM, KEEP_TO))
        deleted = cur.rowcount
        print(f"  {client}: deleted {deleted:,} rows")

    conn.commit()

    # Verify what remains
    print("\n--- Remaining data ---")
    for client in CLIENTS:
        cur.execute("""
            SELECT MIN(report_date), MAX(report_date), COUNT(*), ROUND(SUM(spend)::numeric, 2)
            FROM raw_search_term_data WHERE client_id = %s
        """, (client,))
        row = cur.fetchone()
        print(f"  {client}: {row[0]} → {row[1]} | {row[2]:,} rows | spend: {row[3]}")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
