import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

def print_negative_reasons():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    
    query = """
    SELECT reason, count(*) 
    FROM actions_log 
    WHERE client_id = 's2c_uae_test' 
      AND action_type = 'NEGATIVE'
    GROUP BY reason
    ORDER BY count DESC
    LIMIT 20;
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string())
    conn.close()

if __name__ == "__main__":
    print_negative_reasons()
