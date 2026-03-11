import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app_core.constants import ACTION_MATURITY_DAYS

def get_db_connection():
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in .env")
    return create_engine(db_url)

def check_cooldown_violations():
    print("Checking for Cooldown Violations in actions_log...")
    engine = get_db_connection()
    
    query = f"""
    WITH bid_changes AS (
        SELECT 
            client_id,
            campaign_name,
            ad_group_name,
            target_text,
            action_date,
            old_value,
            new_value
        FROM actions_log
        WHERE action_type = 'BID_CHANGE'
          AND client_id = 's2c_uae_test'
    ),
    ordered_changes AS (
        SELECT 
            *,
            LAG(action_date) OVER (PARTITION BY client_id, campaign_name, ad_group_name, target_text ORDER BY action_date) as prev_action_date,
            LAG(new_value) OVER (PARTITION BY client_id, campaign_name, ad_group_name, target_text ORDER BY action_date) as prev_new_value
        FROM bid_changes
    )
    SELECT 
        client_id,
        campaign_name,
        ad_group_name,
        target_text,
        prev_action_date,
        action_date,
        EXTRACT(EPOCH FROM (action_date - prev_action_date))/86400.0 as days_between,
        prev_new_value as previous_adjusted_bid,
        old_value as bid_before_second_change,
        new_value as final_bid
    FROM ordered_changes
    WHERE prev_action_date IS NOT NULL 
      AND EXTRACT(EPOCH FROM (action_date - prev_action_date))/86400.0 < {ACTION_MATURITY_DAYS}
    ORDER BY days_between ASC
    """
    
    df = pd.read_sql(query, engine)
    
    if df.empty:
        print(f"No cooldown violations found! All BID_CHANGE actions are spaced by at least {ACTION_MATURITY_DAYS} days.")
    else:
        print(f"Found {len(df)} instances where a target received multiple BID_CHANGE actions within {ACTION_MATURITY_DAYS} days.")
        
        # Output summary by client
        summary = df.groupby('client_id').size().reset_index(name='violations_count')
        print("\\nViolations by Client:")
        print(summary.to_string(index=False))
        
        df.to_csv('cooldown_violations.csv', index=False)
        print("\\nDetailed list saved to cooldown_violations.csv")
        
        print("\\nSample of violations (Top 5 fastest back-to-back changes):")
        display_cols = ['client_id', 'target_text', 'days_between', 'previous_adjusted_bid', 'bid_before_second_change', 'final_bid']
        print(df[display_cols].head(5).to_string(index=False))

if __name__ == "__main__":
    check_cooldown_violations()
