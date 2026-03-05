import psycopg2
import pandas as pd
from datetime import timedelta, datetime
import sys
import os

# Configuration
CLIENT_ID = 's2c_uae_test'
DATABASE_URL = "postgresql://postgres.wuakeiwxkjvhsnmkzywz:Zen%40rise%40123%21@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
# Looking at longer window to get robust training data (Dec + Jan)
START_DATE = '2025-12-01'
END_DATE = '2026-01-31'
WINDOW_DAYS = 30 # 30d Pre, 30d Post

def analyze_efficiency_decline():
    print(f"--- Counterfactual Analysis: Establishing Efficiency Decline Factor ---")
    print(f"Training Set: {START_DATE} to {END_DATE} (Confirmed Winners Only)")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 1. Get Harvest Actions
    query_actions = f"""
        SELECT 
            action_date, 
            target_text, 
            campaign_name as source_campaign
        FROM actions_log 
        WHERE client_id = '{CLIENT_ID}' 
          AND action_type = 'HARVEST'
          AND action_date >= '{START_DATE}' 
          AND action_date <= '{END_DATE}'
        ORDER BY action_date DESC
    """
    actions_df = pd.read_sql_query(query_actions, conn)
    actions_df['action_date'] = pd.to_datetime(actions_df['action_date'])
    
    # 2. Get All Stats
    query_stats = f"""
        SELECT 
            start_date as date,
            target_text,
            customer_search_term,
            match_type,
            impressions,
            clicks,
            orders,
            spend,
            sales
        FROM target_stats
        WHERE client_id = '{CLIENT_ID}'
    """
    stats_df = pd.read_sql_query(query_stats, conn)
    stats_df['date'] = pd.to_datetime(stats_df['date'])
    
    def normalize(s):
        return str(s).lower().strip().replace('"', '').replace("'", "")
    
    actions_df['norm_target'] = actions_df['target_text'].apply(normalize)
    stats_df['norm_target'] = stats_df['target_text'].apply(normalize)
    stats_df['norm_cst'] = stats_df['customer_search_term'].apply(normalize)
    stats_df['norm_match'] = stats_df['match_type'].apply(lambda x: str(x).lower().strip())
    
    training_data = []

    for idx, row in actions_df.iterrows():
        norm_term = row['norm_target']
        action_date = row['action_date']
        
        # --- AFTER (Destination) ---
        post_start = action_date
        post_end = action_date + timedelta(days=WINDOW_DAYS)
        post_mask = (
            (stats_df['norm_target'] == norm_term) & 
            (stats_df['norm_match'] == 'exact') & 
            (stats_df['date'] > post_start) & 
            (stats_df['date'] <= post_end)
        )
        post_stats = stats_df[post_mask]
        sales_after = post_stats['sales'].sum()
        spend_after = post_stats['spend'].sum()
        
        # FILTER: MUST BE CONFIRMED WINNER (Has Sales)
        if sales_after == 0:
            continue
            
        roas_after = sales_after / spend_after if spend_after > 0 else 0

        # --- BEFORE (Source) ---
        pre_start = action_date - timedelta(days=90)
        pre_end = action_date
        pre_mask = (
            (stats_df['date'] >= pre_start) & 
            (stats_df['date'] < pre_end) & 
            (
                (stats_df['norm_cst'] == norm_term) | 
                (stats_df['norm_target'] == norm_term)
            )
        )
        pre_stats = stats_df[pre_mask]
        sales_before = pre_stats['sales'].sum()
        spend_before = pre_stats['spend'].sum()
        
        # FILTER: MUST HAVE HISTORY TO COMPARE
        if sales_before == 0:
            continue
            
        roas_before = sales_before / spend_before if spend_before > 0 else 0
        
        training_data.append({
            'Term': row['target_text'],
            'Time': action_date.strftime('%Y-%m'),
            'Sales_Before': sales_before, # 90d Total
            'Sales_After': sales_after,   # 30d Total
            'Spend_Before': spend_before,
            'Spend_After': spend_after,
            'ROAS_Before': roas_before,
            'ROAS_After': roas_after,
            'Efficiency_Ratio': roas_after / roas_before if roas_before > 0 else 0
        })

    conn.close()
    
    df = pd.DataFrame(training_data)
    
    if not df.empty:
        print(f"\n=== TRAINING SET (Winners Only: Dec & Jan) ===")
        print(df[['Term', 'Time', 'ROAS_Before', 'ROAS_After', 'Efficiency_Ratio']].to_markdown(index=False, floatfmt=".2f"))

        # Calculate "Decline Factor"
        # Option 1: Simple Average of Ratios
        avg_ratio = df['Efficiency_Ratio'].mean()
        
        # Option 2: Weighted Average (Total After Sales / Total Before Implied) - Better for Portfolio
        # Actually simplest is Ratio of Aggregates
        total_roas_before = df['Sales_Before'].sum() / df['Spend_Before'].sum()
        total_roas_after = df['Sales_After'].sum() / df['Spend_After'].sum()
        weighted_ratio = total_roas_after / total_roas_before
        
        print(f"\n=== DERIVED FACTORS (n={len(df)}) ===")
        print(f"Agg. ROAS Before: {total_roas_before:.2f}")
        print(f"Agg. ROAS After:  {total_roas_after:.2f}")
        print(f"Decline Factor (Weighted): {weighted_ratio:.3f}x")
        print(f"Decline Factor (Simple Avg): {avg_ratio:.3f}x")
        
        print(f"\nThis means we expect Efficiency to drop to {weighted_ratio*100:.1f}% of its source value upon harvest.")
        print(f"Any performance ABOVE this baseline ({total_roas_before * weighted_ratio:.2f} ROAS) is value added.")
        
    else:
        print("No training data found (No winners with history).")

if __name__ == "__main__":
    analyze_efficiency_decline()
