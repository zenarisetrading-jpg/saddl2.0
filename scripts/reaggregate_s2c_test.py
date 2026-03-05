#!/usr/bin/env python3
"""
Direct SQL reaggregation for s2c_test - bypasses broken function.
"""

import os
import sys
import psycopg2

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

def main():
    client_id = "s2c_test"
    db_url = os.environ.get("DATABASE_URL") or "postgresql://postgres.wuakeiwxkjvhsnmkzywz:Zen%40rise%40123%21@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
    
    print(f"🔄 Starting direct reaggregation for client: {client_id}")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Step 1: Find weeks in raw_search_term_data
        cursor.execute("""
            SELECT DISTINCT date_trunc('week', report_date)::date as week_start
            FROM raw_search_term_data
            WHERE client_id = %s
            ORDER BY week_start DESC
        """, (client_id,))
        weeks = [row[0] for row in cursor.fetchall()]
        print(f"Found {len(weeks)} weeks to reaggregate: {weeks}")
        
        # Step 2: For each week, aggregate and upsert
        total_rows = 0
        for week_start in weeks:
            print(f"\n  Processing week: {week_start}...")
            
            # Delete existing rows for this week
            cursor.execute("""
                DELETE FROM target_stats 
                WHERE client_id = %s AND start_date = %s
            """, (client_id, week_start))
            deleted = cursor.rowcount
            print(f"    Deleted {deleted} existing rows")
            
            # Insert aggregated data (without end_date column)
            cursor.execute("""
                INSERT INTO target_stats 
                (client_id, start_date, campaign_name, ad_group_name, target_text, 
                 customer_search_term, match_type, spend, sales, orders, clicks, impressions)
                SELECT 
                    client_id,
                    date_trunc('week', report_date)::date as start_date,
                    campaign_name,
                    ad_group_name,
                    COALESCE(targeting, customer_search_term) as target_text,
                    customer_search_term,
                    match_type,
                    SUM(spend) as spend,
                    SUM(sales) as sales,
                    SUM(orders) as orders,
                    SUM(clicks) as clicks,
                    SUM(impressions) as impressions
                FROM raw_search_term_data
                WHERE client_id = %s 
                  AND date_trunc('week', report_date)::date = %s
                GROUP BY 
                    client_id, 
                    date_trunc('week', report_date)::date,
                    campaign_name, 
                    ad_group_name, 
                    COALESCE(targeting, customer_search_term),
                    customer_search_term,
                    match_type
                ON CONFLICT (client_id, start_date, campaign_name, ad_group_name, target_text, customer_search_term)
                DO UPDATE SET
                    match_type = EXCLUDED.match_type,
                    spend = EXCLUDED.spend,
                    sales = EXCLUDED.sales,
                    orders = EXCLUDED.orders,
                    clicks = EXCLUDED.clicks,
                    impressions = EXCLUDED.impressions,
                    updated_at = CURRENT_TIMESTAMP
            """, (client_id, week_start))
            inserted = cursor.rowcount
            total_rows += inserted
            print(f"    Inserted {inserted} aggregated rows")
        
        conn.commit()
        print(f"\n✅ Reaggregation complete! Total rows affected: {total_rows}")
        
        # Verify the new date range
        print("\n📊 Updated TARGET STATS Date Range:")
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
        
        # Show latest weeks
        print("\n📅 Latest Weeks in TARGET STATS:")
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
            LIMIT 5
        """, (client_id,))
        rows = cursor.fetchall()
        print(f"  {'Week Start':<12} {'Rows':>8} {'Clicks':>10} {'Spend':>12}")
        print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*12}")
        for row in rows:
            print(f"  {str(row[0]):<12} {row[1]:>8,} {row[2]:>10,} ${row[3]:>10,.2f}")
        
        conn.close()
        print("\n" + "=" * 60)
        print("✅ Account data is now up to date!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
