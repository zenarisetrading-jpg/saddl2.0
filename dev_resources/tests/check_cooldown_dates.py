import os
import sys
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from app_core.db_manager import get_db_manager

load_dotenv()

def check():
    db = get_db_manager()
    print("Checking action dates...")
    query1 = "SELECT MAX(action_date) FROM actions_log WHERE client_id = 's2c_uae_test'"
    with db._get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query1)
            res1 = cursor.fetchone()
            print(f"Max action date s2c_uae_test: {res1[0]}")
            
    query2 = "SELECT MAX(start_date) FROM target_stats WHERE client_id = 's2c_uae_test'"
    with db._get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query2)
            res2 = cursor.fetchone()
            print(f"Max target stats date s2c_uae_test: {res2[0]}")
            
    print("\\nRunning record_action_outcomes for s2c_uae_test...")
    updated_count = db.record_action_outcomes("s2c_uae_test")
    print(f"Rows updated by record_action_outcomes: {updated_count}")
    
    if updated_count > 0:
        print("\\nSample of updated rows:")
        query3 = "SELECT action_date, target_text, outcome_roas_delta, outcome_label FROM actions_log WHERE client_id = 's2c_uae_test' AND outcome_label IS NOT NULL LIMIT 10"
        with db._get_connection() as conn:
            df = pd.read_sql(query3, conn)
            print(df)

if __name__ == "__main__":
    check()
