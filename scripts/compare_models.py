import os
import pandas as pd
import numpy as np
import sys

# Add desktop module to path so we can import the existing logic
sys.path.append(os.path.join(os.path.dirname(__file__), 'desktop'))

try:
    from features.optimizer_shared.strategies.bids import calculate_bid_optimizations
    from app_core.data_hub import DataHub
except ImportError as e:
    print(f"Warning: Could not import existing optimizer: {e}")
    # Define a mock if we can't import
    def calculate_bid_optimizations(df, config, *args, **kwargs):
        df_out = df.copy()
        df_out['New Bid'] = df_out.get('Current Bid', 1.0) * 1.1 # Dummy
        return df_out, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

from sqlalchemy import create_engine
from dotenv import load_dotenv
import warnings
warnings.filterwarnings('ignore')

def get_db_connection():
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment variables. Please check your .env file.")
    return create_engine(db_url)

def run_rules_engine_for_targets(ml_recs_df, engine):
    print("\\n--- Running Rules Engine ---")
    
    if ml_recs_df.empty:
        return pd.DataFrame()

    # Get the unique client_ids
    client_ids = ml_recs_df['client_id'].unique()
    
    # We need to construct a dataframe in the format expected by calculate_bid_optimizations
    # The existing logic expects: Customer Search Term, Targeting, Campaign Name, Ad Group Name, 
    # Match Type, Spend, Sales, Clicks, Impressions, Orders, Current Bid, etc.
    
    # Let's fetch the latest performance data for these targets
    client_id_str = "','".join([str(c) for c in client_ids])
    query = f"""
        SELECT client_id, campaign_name, ad_group_name, target_text, match_type,
               SUM(impressions) as "Impressions", 
               SUM(clicks) as "Clicks", 
               SUM(spend) as "Spend", 
               SUM(sales) as "Sales", 
               SUM(orders) as "Orders"
        FROM target_stats
        WHERE client_id IN ('{client_id_str}')
        AND start_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY client_id, campaign_name, ad_group_name, target_text, match_type
    """
    
    try:
        perf_data = pd.read_sql(query, engine)
        
        # Format for rules engine
        rules_input = perf_data.rename(columns={
            'campaign_name': 'Campaign Name',
            'ad_group_name': 'Ad Group Name',
            'target_text': 'Targeting',
            'match_type': 'Match Type'
        })
        
        # Merge current bid from ML recs to use as base
        bid_mapping = ml_recs_df[['client_id', 'campaign_name', 'ad_group_name', 'target_text', 'current_bid']]
        rules_input = rules_input.merge(
            bid_mapping, 
            left_on=['client_id', 'Campaign Name', 'Ad Group Name', 'Targeting'],
            right_on=['client_id', 'campaign_name', 'ad_group_name', 'target_text'],
            how='inner'
        )
        rules_input['Current Bid'] = rules_input['current_bid']
        
        # Calculate derived metrics before passing to rules engine
        rules_input['ROAS'] = np.where(rules_input['Spend'] > 0, rules_input['Sales'] / rules_input['Spend'], 0.0)
        rules_input['CPC'] = np.where(rules_input['Clicks'] > 0, rules_input['Spend'] / rules_input['Clicks'], 0.0)
        
        config = {
            "TARGET_ROAS": 2.5,
            "BID_UP_THROTTLE": 0.50,
            "BID_DOWN_THROTTLE": 0.50,
            "MAX_BID_CHANGE": 0.25,
            "MIN_CLICKS_EXACT": 5,
            "MIN_CLICKS_PT": 5,
            "MIN_CLICKS_BROAD": 10,
            "MIN_CLICKS_AUTO": 10
        }
        
        bids_exact, bids_pt, bids_agg, bids_auto = calculate_bid_optimizations(
            rules_input, config, data_days=30
        )
        
        all_rules_preds = pd.concat([bids_exact, bids_pt, bids_agg, bids_auto], ignore_index=True)
        
        if not all_rules_preds.empty:
            # Format back to join keys
            all_rules_preds = all_rules_preds.rename(columns={
                'Campaign Name': 'campaign_name',
                'Ad Group Name': 'ad_group_name',
                'Targeting': 'target_text'
            })
            
            # Need to get client_id back (approximate based on the original data)
            rules_output = pd.merge(
                bid_mapping,
                all_rules_preds[['campaign_name', 'ad_group_name', 'target_text', 'New Bid', 'Reason']],
                on=['campaign_name', 'ad_group_name', 'target_text'],
                how='inner'
            )
            
            rules_output = rules_output.rename(columns={'New Bid': 'rules_recommended_bid', 'Reason': 'rules_reason'})
            return rules_output
            
        return pd.DataFrame()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error running rules engine: {e}")
        raise

def compare_models():
    print("Starting Model Comparison...")
    
    if not os.path.exists('ml_recs_v2.csv'):
        print("ml_recs_v2.csv not found. Please run ml_bid_optimizer.py first.")
        return
        
    ml_recs = pd.read_csv('ml_recs_v2.csv')
    if ml_recs.empty:
        print("ml_recs_v2.csv is empty.")
        return
        
    engine = get_db_connection()
    
    # Run existing rules engine
    rules_recs = run_rules_engine_for_targets(ml_recs, engine)
    
    if rules_recs.empty:
        print("Warning: Rules engine produced no recommendations.")
        return
        
    # Join the findings
    join_keys = ['client_id', 'campaign_name', 'ad_group_name', 'target_text']
    comparison = pd.merge(ml_recs, rules_recs, on=join_keys, how='inner')
    
    # Drop duplicated current_bid_y if it exists
    if 'current_bid_y' in comparison.columns:
        comparison = comparison.drop('current_bid_y', axis=1).rename(columns={'current_bid_x': 'current_bid'})
    
    if comparison.empty:
        print("No overlap between ML and Rules recommendations.")
        return
        
    # Define directions for Rules
    def get_rules_direction(row):
        if pd.isna(row['rules_recommended_bid']): return 'hold'
        if row['rules_recommended_bid'] > row['current_bid']: return 'increase'
        if row['rules_recommended_bid'] < row['current_bid']: return 'decrease'
        return 'hold'
        
    comparison['rules_direction'] = comparison.apply(get_rules_direction, axis=1)
    
    # Define directions for ML (already have predicted_roas_direction but let's re-verify)
    def get_ml_direction(row):
        if pd.isna(row['recommended_bid']): return 'hold'
        if row['recommended_bid'] > row['current_bid']: return 'increase'
        if row['recommended_bid'] < row['current_bid']: return 'decrease'
        return 'hold'
        
    comparison['ml_direction'] = comparison.apply(get_ml_direction, axis=1)
    
    # Calculate agreement
    comparison['agreement'] = comparison['ml_direction'] == comparison['rules_direction']
    
    agreement_rate = comparison['agreement'].mean() * 100
    
    # Magnitudes
    comparison['ml_magnitude_pct'] = ((comparison['recommended_bid'] - comparison['current_bid']) / comparison['current_bid']).abs() * 100
    comparison['rules_magnitude_pct'] = ((comparison['rules_recommended_bid'] - comparison['current_bid']) / comparison['current_bid']).abs() * 100
    
    avg_ml_mag = comparison['ml_magnitude_pct'].mean()
    avg_rules_mag = comparison['rules_magnitude_pct'].mean()
    
    print("\\n" + "="*50)
    print("MODEL COMPARISON SUMMARY")
    print("="*50)
    print(f"Total targets compared: {len(comparison)}")
    print(f"Agreement rate (same direction): {agreement_rate:.1f}%")
    print(f"Average ML absolute bid change: {avg_ml_mag:.1f}%")
    print(f"Average Rules absolute bid change: {avg_rules_mag:.1f}%")
    
    ml_coverage = len(ml_recs)
    rules_coverage = len(rules_recs)
    print(f"\\nCoverage - ML Engine: {ml_coverage} recommendations")
    print(f"Coverage - Rules Engine: {rules_coverage} recommendations")
    
    # Disagreements
    print("\\n--- Disagreement Flags ---")
    opposite_mask = (
        ((comparison['ml_direction'] == 'increase') & (comparison['rules_direction'] == 'decrease')) |
        ((comparison['ml_direction'] == 'decrease') & (comparison['rules_direction'] == 'increase'))
    )
    
    disagreements = comparison[opposite_mask]
    print(f"Found {len(disagreements)} targets with OPPOSITE recommendations.")
    
    if not disagreements.empty:
        # High confidence disagreements
        high_conf_disagreements = disagreements[disagreements['model_confidence'] > 0.7]
        print(f"Of those, {len(high_conf_disagreements)} have HIGH ML confidence (>0.70).")
        
        if not high_conf_disagreements.empty:
            print("\\nTop 5 High Confidence Disagreements:")
            display_cols = ['campaign_name', 'target_text', 'current_bid', 'recommended_bid', 'rules_recommended_bid', 'model_confidence']
            print(high_conf_disagreements.sort_values('model_confidence', ascending=False).head(5)[display_cols].to_string())
    
    comparison.to_csv('model_comparison_v2.csv', index=False)
    print("\\nDetailed comparison saved to model_comparison_v2.csv")

if __name__ == "__main__":
    compare_models()
