
"""
Migration: Move S2C accounts to 'S2C-Test' Organization
=======================================================
Moves 's2c_test' and 's2c_uae_test' accounts to a new dedicated organization 'S2C-Test'.
"""

import os
import sys
import uuid
from pathlib import Path

# Add desktop to path
desktop_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if desktop_path not in sys.path:
    sys.path.insert(0, desktop_path)

from app_core.db_manager import get_db_manager

def run_migration():
    print("MIGRATE: Starting S2C account migration...")
    
    # Force load .env from correct path if not loaded
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env' # saddle/.env
    load_dotenv(env_path)
    
    db = get_db_manager()
    print(f"MIGRATE: DB Manager Type: {type(db).__name__}")
    
    # 1. Create/Ensure Target Organization exists
    target_org_name = "S2C-Test"
    # Create a deterministic ID for this org so we don't create duplicates
    target_org_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "s2c-test.saddle.io"))
    
    print(f"MIGRATE: Target Org: {target_org_name} (ID: {target_org_id})")
    
    try:
        ph = db.placeholder
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Ensure Org Exists
            print("MIGRATE: Upserting Organization...")
            # Note: Postgres 'ON CONFLICT' syntax vs SQLite 'INSERT OR REPLACE'
            # Assuming Postgres context mostly, but let's try to be generic or detect
            
            is_postgres = "Postgres" in type(db).__name__
            
            if is_postgres:
                cursor.execute(f"""
                    INSERT INTO organizations (id, name, type, status) 
                    VALUES ({ph}, {ph}, 'SELLER', 'ACTIVE')
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """, (target_org_id, target_org_name))
            else:
                # SQLite fallback (simplified)
                cursor.execute(f"""
                    INSERT OR REPLACE INTO organizations (id, name, type, status) 
                    VALUES ({ph}, {ph}, 'SELLER', 'ACTIVE')
                """, (target_org_id, target_org_name))
                
            print(f"MIGRATE: Organization '{target_org_name}' ensured.")
            
            # 2. Update Accounts
            accounts_to_move = ['s2c_test', 's2c_uae_test']
            updated_count = 0
            
            for account_id in accounts_to_move:
                print(f"MIGRATE: Moving account '{account_id}'...")
                cursor.execute(f"""
                    UPDATE accounts 
                    SET organization_id = {ph}
                    WHERE account_id = {ph}
                """, (target_org_id, account_id))
                
                if cursor.rowcount > 0:
                    print(f"MIGRATE: ✅ Moved '{account_id}'")
                    updated_count += cursor.rowcount
                else:
                    print(f"MIGRATE: ⚠️ Account '{account_id}' not found in DB.")
            
            print(f"MIGRATE: Complete! Total accounts moved: {updated_count}")

    except Exception as e:
        print(f"MIGRATE ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()
