import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
from datetime import timedelta

def get_db_connection():
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in .env")
    return create_engine(db_url)

def run_analysis():
    print("Starting Detailed Account-Level Analysis for s2c_uae_test and s2c_test...")
    
    # 1. Load the comparison outputs from the previous steps
    if not os.path.exists('model_comparison_v2.csv'):
        print("Error: model_comparison_v2.csv not found. Please run ml_bid_optimizer.py and compare_models.py first.")
        return
        
    comp_df = pd.read_csv('model_comparison_v2.csv')
    
    # 2. Connect to the DB and pull the last 45 days of stats for active targets
    engine = get_db_connection()
    clients = ['s2c_uae_test', 's2c_test']
    client_str = "','".join(clients)
    
    query = f"""
        SELECT client_id, start_date, campaign_name, ad_group_name, target_text, match_type,
               impressions, clicks, spend, sales, orders
        FROM target_stats
        WHERE client_id IN ('{client_str}')
        AND start_date >= CURRENT_DATE - INTERVAL '45 days'
    """
    
    print(f"Executing query to fetch 45-day history for {clients}...")
    stats_df = pd.read_sql(query, engine)
    stats_df['start_date'] = pd.to_datetime(stats_df['start_date'])
    for col in ['impressions', 'clicks', 'spend', 'sales', 'orders']:
        stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
        
    # 3. Calculate 45-day actual performance metrics per target
    grouped_45d = stats_df.groupby(['client_id', 'campaign_name', 'ad_group_name', 'target_text']).agg({
        'clicks': 'sum',
        'spend': 'sum',
        'sales': 'sum',
        'orders': 'sum',
        'impressions': 'sum'
    }).reset_index()
    
    grouped_45d['45d_acos'] = np.where(grouped_45d['sales'] > 0, grouped_45d['spend'] / grouped_45d['sales'], 0)
    grouped_45d['45d_roas'] = np.where(grouped_45d['spend'] > 0, grouped_45d['sales'] / grouped_45d['spend'], 0)
    grouped_45d['45d_cvr'] = np.where(grouped_45d['clicks'] > 0, grouped_45d['orders'] / grouped_45d['clicks'], 0)
    
    # 4. Pull 30-day performance history trend (Weekly ROAS blocks to see moving trend)
    # Get the max date to anchor the 'last 30 days'
    max_date = stats_df['start_date'].max()
    if pd.isna(max_date):
        max_date = pd.Timestamp.now()
        
    stats_30d = stats_df[stats_df['start_date'] >= (max_date - timedelta(days=30))].copy()
    
    # We will compute ROAS for 3 x 10-day windows to establish a trend without overwhelming the CSV
    stats_30d['window'] = pd.cut(
        (max_date - stats_30d['start_date']).dt.days,
        bins=[-1, 10, 20, 31],
        labels=['Days 0-10 (Recent)', 'Days 11-20', 'Days 21-30']
    )
    
    trend_grouped = stats_30d.groupby(['client_id', 'campaign_name', 'ad_group_name', 'target_text', 'window'], observed=False).agg({
        'spend': 'sum', 'sales': 'sum'
    }).reset_index()
    
    trend_grouped['window_roas'] = np.where(trend_grouped['spend'] > 0, trend_grouped['sales'] / trend_grouped['spend'], 0)
    
    # Pivot so we get one row per target with the 3 windows
    trend_pivot = trend_grouped.pivot(
        index=['client_id', 'campaign_name', 'ad_group_name', 'target_text'],
        columns='window',
        values='window_roas'
    ).reset_index()
    
    # Clean up column names from pivot
    trend_pivot.columns.name = None
    
    def determine_trend(row):
        w3 = row['Days 21-30']
        w2 = row['Days 11-20']
        w1 = row['Days 0-10 (Recent)']
        
        # Simple heuristic
        if w1 > w2 and w2 > w3 and w1 > 0:
            return "Improving"
        elif w1 < w2 and w2 < w3:
            return "Declining"
        elif w1 == w2 == w3 == 0:
            return "Flat (Zero)"
        else:
            return "Mixed/Volatile"
            
    trend_pivot['30d_ROAS_Trend_Classification'] = trend_pivot.apply(determine_trend, axis=1)
    
    # 5. Join everything together into the final analysis dataframe
    analysis_df = pd.merge(comp_df, grouped_45d, on=['client_id', 'campaign_name', 'ad_group_name', 'target_text'], how='left')
    analysis_df = pd.merge(analysis_df, trend_pivot, on=['client_id', 'campaign_name', 'ad_group_name', 'target_text'], how='left')
    
    # Organize columns for side-by-side readability
    cols_to_keep = [
        'client_id', 'campaign_name', 'ad_group_name', 'target_text', 'match_type',
        # Actual Stats
        'spend', 'sales', 'clicks', 'orders', '45d_acos', '45d_roas', '45d_cvr',
        # Rules Output
        'current_bid', 'rules_recommended_bid', 'rules_reason', 'rules_direction',
        # ML Output
        'recommended_bid', 'model_confidence', 'ml_direction',
        # Comparison
        'agreement',
        # 30-day Trend
        'Days 21-30', 'Days 11-20', 'Days 0-10 (Recent)', '30d_ROAS_Trend_Classification'
    ]
    
    # Keep only available columns to prevent key errors
    final_cols = [c for c in cols_to_keep if c in analysis_df.columns]
    final_df = analysis_df[final_cols]
    
    # Filter out any totally empty ones just in case
    final_df = final_df[final_df['target_text'].notna()]
    
    # 6. Output to CSV
    output_file = 's2c_analysis.csv'
    final_df.to_csv(output_file, index=False)
    print(f"\\nSaved detailed target analysis to {output_file}")
    
    # 7. Print custom summary requested
    print("\\n" + "="*60)
    print("DISAGREEMENT IMPACT SUMMARY")
    print("="*60)
    
    # Group 1: ML says Increase, Rules says Decrease
    mask_ml_up_rules_down = (final_df['ml_direction'] == 'increase') & (final_df['rules_direction'] == 'decrease')
    group1 = final_df[mask_ml_up_rules_down]
    
    # Group 2: ML says Decrease, Rules says Increase
    mask_ml_down_rules_up = (final_df['ml_direction'] == 'decrease') & (final_df['rules_direction'] == 'increase')
    group2 = final_df[mask_ml_down_rules_up]
    
    avg_roas_g1 = group1['45d_roas'].mean() if len(group1) > 0 else 0
    avg_roas_g2 = group2['45d_roas'].mean() if len(group2) > 0 else 0
    
    print(f"SCENARIO 1: ML says INCREASE, Rules says DECREASE")
    print(f"  - Number of targets: {len(group1)}")
    print(f"  - Average Actual 45d ROAS: {avg_roas_g1:.2f}x")
    if len(group1) > 0:
        print(f"  - Average Clicks: {group1['clicks'].mean():.1f}, Average Spend: {group1['spend'].mean():.2f}")
    
    print(f"\\nSCENARIO 2: ML says DECREASE, Rules says INCREASE")
    print(f"  - Number of targets: {len(group2)}")
    print(f"  - Average Actual 45d ROAS: {avg_roas_g2:.2f}x")
    if len(group2) > 0:
        print(f"  - Average Clicks: {group2['clicks'].mean():.1f}, Average Spend: {group2['spend'].mean():.2f}")
        
    print("\\nInterpretation:")
    print("If targets in Scenario 1 have HIGH actual ROAS, the ML model is correctly identifying winners that the rules engine is unfairly punishing.")
    print("If targets in Scenario 2 have HIGH actual ROAS, the rules engine is correctly identifying winners that the ML model is missing.")

if __name__ == "__main__":
    run_analysis()
