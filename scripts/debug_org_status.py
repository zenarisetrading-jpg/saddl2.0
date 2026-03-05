
import sys
import os
from pathlib import Path

# Force python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force env load
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

from app_core.db_manager import get_db_manager
import pandas as pd

def check_org_status():
    db = get_db_manager()
    print(f"DEBUG: Connected to {type(db).__name__}")
    
    try:
        with db._get_connection() as conn:
            # Postgres vs SQLite handling
            query = "SELECT account_id, account_name, organization_id FROM accounts"
            
            if hasattr(db, 'db_url'): # Postgres
                 df = pd.read_sql(query, conn)
            else: # SQLite
                 df = pd.read_sql(query, conn)
            
            print("\n--- CURRENT ACCOUNT STATUS ---")
            print(df.to_string())
            print("------------------------------\n")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_org_status()
