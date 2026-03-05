import sys
import os
import time
sys.path.insert(0, os.path.abspath('.'))
from app_core.db_manager import get_db_manager
import pandas as pd
from dotenv import load_dotenv
load_dotenv(".env")

db = get_db_manager(False)
client_id = "s2c_uae_test"
t0 = time.time()
with db._get_connection() as conn:
    df = pd.read_sql("""
        SELECT
            report_date AS "Date",
            campaign_name AS "Campaign Name",
            ad_group_name AS "Ad Group Name",
            targeting AS "Targeting",
            customer_search_term AS "Customer Search Term",
            match_type AS "Match Type",
            spend AS "Spend",
            sales AS "Sales",
            orders AS "Orders",
            clicks AS "Clicks",
            impressions AS "Impressions"
        FROM raw_search_term_data
        WHERE client_id = %s
        ORDER BY report_date DESC
    """, conn, params=(client_id,))
    if not df.empty and 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
print(f"Old approach: {time.time()-t0:.2f}s, shape: {df.shape}")

t1 = time.time()
with db._get_connection() as conn:
    df2 = pd.read_sql("""
        SELECT
            report_date AS "Date",
            customer_search_term AS "Customer Search Term",
            SUM(spend) AS "Spend",
            SUM(sales) AS "Sales"
        FROM raw_search_term_data
        WHERE client_id = %s
          AND report_date >= CURRENT_DATE - INTERVAL '65 days'
        GROUP BY report_date, customer_search_term
    """, conn, params=(client_id,))
    if not df2.empty and 'Date' in df2.columns:
        df2['Date'] = pd.to_datetime(df2['Date'])
print(f"New approach: {time.time()-t1:.2f}s, shape: {df2.shape}")
