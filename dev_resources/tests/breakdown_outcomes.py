import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

def get_breakdown():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    
    query = """
    SELECT 
        CASE 
            WHEN reason ILIKE '%Visibility Boost%' THEN 'Visibility Boost'
            WHEN new_value::numeric > old_value::numeric THEN 'Bid Increase'
            WHEN new_value::numeric < old_value::numeric THEN 'Bid Decrease'
            ELSE 'Unknown/Hold'
        END as action_category,
        outcome_label,
        COUNT(*) as count
    FROM actions_log 
    WHERE client_id = 's2c_uae_test' 
      AND outcome_label IS NOT NULL 
      AND action_type = 'BID_CHANGE'
    GROUP BY action_category, outcome_label
    ORDER BY action_category, count DESC;
    """
    
    df = pd.read_sql(query, conn)
    
    print("Outcome Breakdown by Specific Action Category:\n")
    if not df.empty:
        pivot_df = df.pivot(index='action_category', columns='outcome_label', values='count').fillna(0).astype(int)
        pivot_df['total'] = pivot_df.sum(axis=1)
        pivot_df = pivot_df.sort_values(by='total', ascending=False)
        print(pivot_df.to_string())
    else:
        print("No labeled outcomes found for client_id 's2c_uae_test'.")
        
    conn.close()

if __name__ == "__main__":
    get_breakdown()
