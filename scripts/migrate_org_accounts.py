
"""
Migration: Assign orphaned accounts to Primary Organization
===========================================================
Moves existing amazon accounts (digiaansh_test, etc.) to the deterministic Primary Organization ID.
This ensures they appear correctly when we enable organization filtering.
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
    print("MIGRATE: Starting account association...")
    
    # Force load .env from correct path if not loaded
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env' # saddle/.env
    load_dotenv(env_path)
    
    db = get_db_manager()
    print(f"MIGRATE: DB Manager Type: {type(db).__name__}")
    if hasattr(db, 'db_url'):
        print(f"MIGRATE: Connected to Postgres (URL found)")
    elif hasattr(db, 'db_path'):
        print(f"MIGRATE: Connected to SQLite: {db.db_path}")

    # Check headers
    total_accounts = 0
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM accounts")
        row = cursor.fetchone()
        if row: 
            # Handle different cursor return types (dict vs tuple)
            total_accounts = row[0] if isinstance(row, tuple) else list(row.values())[0]
            
    print(f"MIGRATE: Total Accounts in DB: {total_accounts}")
    
    # Calculate Primary Org ID (Determinisitc)
    primary_org_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "saddle.io"))
    print(f"MIGRATE: Target Primary Org ID: {primary_org_id}")
    
    accounts_to_update = [
        'digiaansh_test',
        'Repro-test-UAE',
        'repro_test_uae', # Handle potential case/ID variance
        's2c_test',
        's2c_uae_test'
    ]
    
    updated_count = 0
    
    try:
        ph = db.placeholder
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Update specific known accounts first
            for account_id in accounts_to_update:
                cursor.execute(f"""
                    UPDATE accounts 
                    SET organization_id = {ph} 
                    WHERE (account_id = {ph} OR account_name = {ph})
                    AND (organization_id IS NULL OR organization_id = '')
                """, (primary_org_id, account_id, account_id))
                
                if cursor.rowcount > 0:
                    print(f"MIGRATE: Updated account {account_id}")
                    updated_count += cursor.rowcount

            # 2. Update ALL accounts to Primary Org (Force Move)
            print("MIGRATE: forcing update on ALL accounts to target Primary Org...")
            cursor.execute(f"""
                UPDATE accounts 
                SET organization_id = {ph}
            """, (primary_org_id,))
            
            if cursor.rowcount > 0:
                print(f"MIGRATE: Updated {cursor.rowcount} accounts (Force Reassigned).")
                updated_count += cursor.rowcount
            
            print(f"MIGRATE: Success! Total accounts moved: {updated_count}")
            
    except Exception as e:
        print(f"MIGRATE ERROR: {e}")

if __name__ == "__main__":
    run_migration()
