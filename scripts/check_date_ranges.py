#!/usr/bin/env python3
"""
Check date ranges for s2c_test in raw_search_term_data and target_stats tables.
"""

import os
import sys
from datetime import date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment from .env file
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env()

import psycopg2
import pandas as pd

def get_db_url():
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        # Fallback to hardcoded URL from test files
        db_url = "postgresql://postgres.wuakeiwxkjvhsnmkzywz:Zen%40rise%40123%21@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
    return db_url

def main():
    client_id = "s2c_test"
    db_url = get_db_url()
    
    print(f"Checking date ranges for client: {client_id}")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check raw_search_term_data date range
        print("\n📊 RAW SEARCH TERM DATA (raw_search_term_data)")
        print("-" * 40)
        cursor.execute("""
            SELECT 
                MIN(report_date) as min_date,
                MAX(report_date) as max_date,
                COUNT(*) as row_count,
                COUNT(DISTINCT report_date) as distinct_dates
            FROM raw_search_term_data 
            WHERE client_id = %s
        """, (client_id,))
        row = cursor.fetchone()
        if row and row[0]:
            print(f"  Min Date: {row[0]}")
            print(f"  Max Date: {row[1]}")
            print(f"  Total Rows: {row[2]:,}")
            print(f"  Distinct Dates: {row[3]}")
        else:
            print("  No data found!")
        
        # Check target_stats date range
        print("\n📊 TARGET STATS (target_stats)")
        print("-" * 40)
        cursor.execute("""
            SELECT 
                MIN(start_date) as min_date,
                MAX(start_date) as max_date,
                COUNT(*) as row_count,
                COUNT(DISTINCT start_date) as distinct_weeks
            FROM target_stats 
            WHERE client_id = %s
        """, (client_id,))
        row = cursor.fetchone()
        if row and row[0]:
            print(f"  Min Date: {row[0]}")
            print(f"  Max Date: {row[1]}")
            print(f"  Total Rows: {row[2]:,}")
            print(f"  Distinct Weeks: {row[3]}")
        else:
            print("  No data found!")
        
        # Show detailed breakdown by week for target_stats
        print("\n📅 TARGET STATS - Weekly Breakdown")
        print("-" * 40)
        cursor.execute("""
            SELECT 
                start_date,
                COUNT(*) as rows,
                SUM(clicks) as total_clicks,
                SUM(spend) as total_spend
            FROM target_stats 
            WHERE client_id = %s
            GROUP BY start_date
            ORDER BY start_date DESC
            LIMIT 10
        """, (client_id,))
        rows = cursor.fetchall()
        print(f"  {'Week Start':<12} {'Rows':>8} {'Clicks':>10} {'Spend':>12}")
        print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*12}")
        for row in rows:
            print(f"  {str(row[0]):<12} {row[1]:>8,} {row[2]:>10,} ${row[3]:>10,.2f}")
        
        # Show detailed breakdown by date for raw data
        print("\n📅 RAW DATA - Daily Breakdown (Last 10 days)")
        print("-" * 40)
        cursor.execute("""
            SELECT 
                report_date,
                COUNT(*) as rows,
                SUM(clicks) as total_clicks,
                SUM(spend) as total_spend
            FROM raw_search_term_data 
            WHERE client_id = %s
            GROUP BY report_date
            ORDER BY report_date DESC
            LIMIT 10
        """, (client_id,))
        rows = cursor.fetchall()
        print(f"  {'Date':<12} {'Rows':>8} {'Clicks':>10} {'Spend':>12}")
        print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*12}")
        for row in rows:
            print(f"  {str(row[0]):<12} {row[1]:>8,} {row[2]:>10,} ${row[3]:>10,.2f}")
        
        conn.close()
        print("\n" + "=" * 60)
        print("✅ Date range check complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
