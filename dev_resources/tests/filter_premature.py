import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

def filter_premature_negatives():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    
    # Get the 90 premature targets
    # We re-run the logic just to get the list of targets
    query_actions = """
    SELECT client_id, action_date, target_text, campaign_name, ad_group_name, reason
    FROM actions_log
    WHERE client_id = 's2c_uae_test'
      AND action_type = 'NEGATIVE'
    """
    actions_df = pd.read_sql(query_actions, conn)
    
    premature_targets = []
    
    for _, row in actions_df.iterrows():
        client_id = row['client_id']
        target_text = row['target_text']
        action_date = row['action_date']
        
        # We only care about after orders to find premature
        a_query_total = """
        SELECT SUM(spend) as spend, SUM(orders) as orders
        FROM target_stats
        WHERE client_id = %s AND target_text = %s AND start_date >= %s AND start_date <= %s + INTERVAL '30 days'
        """
        
        with conn.cursor() as cur:
            cur.execute(a_query_total, (client_id, target_text, action_date, action_date))
            a_res = cur.fetchone()
            a_orders = float(a_res[1] or 0)
            
        if a_orders > 0:
            premature_targets.append({
                'client_id': client_id,
                'target_text': target_text,
                'action_date': action_date,
                'campaign_name': row['campaign_name']
            })
            
    premature_df = pd.DataFrame(premature_targets)
    print(f"Total initially classified as premature: {len(premature_df)}")
    
    # Now check for corresponding HARVEST actions
    harvests_found = 0
    true_premature = []
    
    for _, row in premature_df.iterrows():
        client_id = row['client_id']
        target_text = row['target_text']
        action_date = row['action_date']
        
        # Check for matching HARVEST within +/- 30 days
        h_query = """
        SELECT count(*)
        FROM actions_log
        WHERE client_id = %s 
          AND target_text = %s 
          AND action_type = 'HARVEST'
          AND action_date >= %s - INTERVAL '30 days'
          AND action_date <= %s + INTERVAL '30 days'
        """
        
        with conn.cursor() as cur:
            cur.execute(h_query, (client_id, target_text, action_date, action_date))
            count = cur.fetchone()[0]
            
        if count > 0:
            harvests_found += 1
        else:
            true_premature.append(row)
            
    print(f"Number of premature negatives that have a matching HARVEST action: {harvests_found}")
    print(f"Remaining TRUE premature performance blocks: {len(true_premature)}")
    
    conn.close()

if __name__ == "__main__":
    filter_premature_negatives()
