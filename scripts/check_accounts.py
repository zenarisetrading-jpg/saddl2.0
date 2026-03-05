
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app_core.db_manager import get_db_manager
import pandas as pd

def check():
    db = get_db_manager()
    print(f"Checking DB: {db.db_path if hasattr(db, 'db_path') else 'Postgres'}")
    
    with db._get_connection() as conn:
        try:
            df = pd.read_sql("SELECT account_id, account_name, organization_id FROM accounts", conn)
            print(df)
        except Exception as e:
            print(e)
            
if __name__ == "__main__":
    check()
