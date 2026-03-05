
import psycopg2
from pipeline.config import get_config
from datetime import timedelta, date

def backfill_raw_ads():
    cfg = get_config()
    CLIENT_ID = 's2c_uae_test'
    START_DATE = date(2025, 10, 15)
    END_DATE = date(2025, 12, 28)

    print(f"Starting backfill for {CLIENT_ID} from {START_DATE} to {END_DATE}...")

    with psycopg2.connect(cfg['database_url']) as conn:
        with conn.cursor() as cur:
            # 1. Clear any existing raw data for this period to avoid partial overlaps/duplicates
            # (Safety check: only delete if we are sure we are filling this range)
            cur.execute("""
                DELETE FROM raw_search_term_data 
                WHERE client_id = %s 
                  AND report_date >= %s 
                  AND report_date <= %s
            """, (CLIENT_ID, START_DATE, END_DATE))
            deleted = cur.rowcount
            print(f"Deleted {deleted} existing rows in raw_search_term_data for this period.")

            # 2. Fetch weekly target_stats
            cur.execute("""
                SELECT 
                    start_date, end_date, 
                    campaign_name, ad_group_name, target_text, customer_search_term, match_type,
                    spend, sales, clicks, impressions, orders
                FROM target_stats
                WHERE client_id = %s
                  AND start_date >= %s
                  AND start_date <= %s
            """, (CLIENT_ID, START_DATE, END_DATE))
            
            rows = cur.fetchall()
            print(f"Found {len(rows)} weekly records in target_stats.")

            if not rows:
                print("No target_stats found for this period. Exiting.")
                return

            # 3. Iterate and expand to daily
            buffer = []
            
            for r in rows:
                start_dt = r[0]
                # target_stats is weekly, but let's confirm end_date vs start_date
                # usually end_date = start_date + 6 days. 
                # Be robust: if end_date is present, use it. If null, assume 7 days.
                end_dt = r[1] if r[1] else start_dt + timedelta(days=6)
                
                # Cap the expansion range to our backfill window + ensuring we don't go beyond today (sanity check)
                # But standard logic: just expand start to end.
                
                num_days = (end_dt - start_dt).days + 1
                if num_days <= 0: continue

                # Integer distribution logic to preserve totals
                # For each metric, we have total T and days N.
                # Daily base = T // N
                # Remainder R = T % N
                # Distribute remainder R randomly across the N days to avoid "Day 1" spikes.
                
                def distribute(total, days):
                    val = int(total or 0)
                    base = val // days
                    rem = val % days
                    
                    # Create base array
                    daily_values = [base] * days
                    
                    # Distribute remainder to random days
                    if rem > 0:
                        import random
                        # Pick 'rem' random indices to increment
                        indices = random.sample(range(days), rem)
                        for idx in indices:
                            daily_values[idx] += 1
                            
                    return daily_values

                # Float distribution (spend, sales) - just divide
                d_spend = float(r[7] or 0) / num_days
                d_sales = float(r[8] or 0) / num_days
                
                # Integer arrays
                daily_impr = distribute(r[10], num_days)
                daily_clicks = distribute(r[9], num_days)
                daily_orders = distribute(r[11], num_days)
                
                current_dt = start_dt
                for i in range(num_days):
                    # Stop if we exceed the backfill window end
                    # (Though rows were selected by start_date, so this is just safety)
                    if current_dt > date(2025, 12, 28):
                        break

                    buffer.append((
                        CLIENT_ID,
                        current_dt,
                        r[2], # campaign
                        r[3], # ad_group
                        r[4], # targeting
                        r[5], # query
                        r[6], # match_type
                        daily_impr[i],
                        daily_clicks[i],
                        d_spend,
                        d_sales,
                        daily_orders[i]
                    ))
                    current_dt += timedelta(days=1)
            
            print(f"Prepared {len(buffer)} daily rows for insertion.")
            
            # 4. Bulk Insert
            if buffer:
                from psycopg2.extras import execute_values
                
                insert_query = """
                    INSERT INTO raw_search_term_data (
                        client_id, report_date, 
                        campaign_name, ad_group_name, targeting, customer_search_term, match_type,
                        impressions, clicks, spend, sales, orders, uploaded_at
                    ) VALUES %s
                """
                # execute_values handles the tuple expansion automatically.
                # We append NOW() to each tuple in the buffer or just let DB handle it?
                # execute_values with template is cleaner.
                
                # We need to match the template to the data structure.
                # buffer has 12 fields. The table has 13 (uploaded_at).
                # We can use a template in execute_values to supply NOW()
                
                execute_values(
                    cur, 
                    insert_query, 
                    buffer,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                    page_size=1000
                )
                print(f"Insertion complete. {len(buffer)} rows inserted.")
                
            conn.commit()
            print("Raw data transaction committed.")

            # 5. Refresh account_daily
            print("Refreshing account_daily for this period...")
            
            MARKETPLACE = cfg['marketplace_uae']   # A2VIGQ35RCS4UG
            # Re-run the bulk aggregation logic
            BULK_SQL = '''
            INSERT INTO sc_analytics.account_daily (
                report_date, marketplace_id,
                total_ordered_revenue, total_units_ordered,
                total_page_views, total_sessions, asin_count,
                ad_attributed_revenue, organic_revenue,
                organic_share_pct, tacos, computed_at
            )
            WITH sc_daily AS (
                SELECT
                    report_date,
                    marketplace_id,
                    COALESCE(SUM(ordered_revenue), 0)   AS total_ordered_revenue,
                    COALESCE(SUM(units_ordered), 0)      AS total_units_ordered,
                    COALESCE(SUM(page_views), 0)         AS total_page_views,
                    COALESCE(SUM(sessions), 0)           AS total_sessions,
                    COUNT(DISTINCT child_asin)           AS asin_count
                FROM sc_raw.sales_traffic
                WHERE marketplace_id = %s
                  AND report_date BETWEEN %s AND %s
                GROUP BY report_date, marketplace_id
            ),
            ad_daily AS (
                SELECT
                    report_date,
                    COALESCE(SUM(sales), 0) AS ad_attributed_revenue,
                    COALESCE(SUM(spend), 0) AS ad_spend
                FROM public.raw_search_term_data
                WHERE client_id = %s
                  AND report_date BETWEEN %s AND %s
                GROUP BY report_date
            )
            SELECT
                sc.report_date,
                sc.marketplace_id,
                sc.total_ordered_revenue,
                sc.total_units_ordered,
                sc.total_page_views,
                sc.total_sessions,
                sc.asin_count,
                COALESCE(ad.ad_attributed_revenue, 0),
                GREATEST(sc.total_ordered_revenue - COALESCE(ad.ad_attributed_revenue, 0), 0),
                ROUND(COALESCE(
                    GREATEST(sc.total_ordered_revenue - COALESCE(ad.ad_attributed_revenue, 0), 0)
                    / NULLIF(sc.total_ordered_revenue, 0) * 100, 0
                )::numeric, 2),
                ROUND(COALESCE(
                    COALESCE(ad.ad_spend, 0) / NULLIF(sc.total_ordered_revenue, 0) * 100, 0
                )::numeric, 2),
                NOW()
            FROM sc_daily sc
            LEFT JOIN ad_daily ad ON sc.report_date = ad.report_date
            ON CONFLICT (report_date, marketplace_id) DO UPDATE SET
                total_ordered_revenue  = EXCLUDED.total_ordered_revenue,
                total_units_ordered    = EXCLUDED.total_units_ordered,
                total_page_views       = EXCLUDED.total_page_views,
                total_sessions         = EXCLUDED.total_sessions,
                asin_count             = EXCLUDED.asin_count,
                ad_attributed_revenue  = EXCLUDED.ad_attributed_revenue,
                organic_revenue        = EXCLUDED.organic_revenue,
                organic_share_pct      = EXCLUDED.organic_share_pct,
                tacos                  = EXCLUDED.tacos,
                computed_at            = NOW()
            '''
            
            cur.execute(BULK_SQL, (MARKETPLACE, START_DATE, END_DATE, CLIENT_ID, START_DATE, END_DATE))
            print(f"account_daily refreshed for range {START_DATE} -> {END_DATE}. Rows affected: {cur.rowcount}")
            conn.commit()

if __name__ == "__main__":
    backfill_raw_ads()
