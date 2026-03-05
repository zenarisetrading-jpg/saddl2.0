import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app_core.postgres_manager import PostgresManager
from dotenv import load_dotenv

def test_digiaansh():
    print("Testing get_latest_raw_data_date for digiaansh_test...")
    
    # Load .env
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(base_path, '.env'))
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in env")
        # Try loading from .env via load_dotenv logic that matches app
        pass
    
    if not db_url:
         # Hard fail if still missing
         print("CRITICAL: Could not find DATABASE_URL even after loading .env")
         return

    db = PostgresManager(db_url)
    
    try:
        # Trigger the fallback path
        date = db.get_latest_raw_data_date('digiaansh_test')
        print(f"Success! Date: {date}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_digiaansh()
