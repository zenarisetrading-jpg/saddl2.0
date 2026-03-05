import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

def print_samples():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    
    query = """
    SELECT new_value, old_value, reason, outcome_label
    FROM actions_log 
    WHERE client_id = 's2c_uae_test' 
      AND outcome_label IS NOT NULL 
      AND action_type = 'BID_CHANGE'
    LIMIT 20;
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string())
        
    conn.close()

if __name__ == "__main__":
    print_samples()
