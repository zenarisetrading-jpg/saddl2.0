
import sys
import os
import uuid
from pathlib import Path
import psycopg2

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv('desktop/.env')

from app_core.auth.service import AuthService
from app_core.db_manager import get_db_manager

def main():
    print("🚀 SADDL - Organization Data Bootstrapper")
    
    # 1. Connect to Postgres (Auth)
    auth_service = AuthService() # Uses basic connection logic
    org_id = None
    org_name = None
    
    try:
        print("Checking Auth Database for Organization...")
        with auth_service._get_connection() as conn:
            with conn.cursor() as cur:
                # Check/Create Organization
                try:
                    cur.execute("SELECT id, name FROM organizations LIMIT 1")
                    row = cur.fetchone()
                    
                    if row:
                        org_id = str(row[0])
                        org_name = row[1]
                        print(f"✅ Found existing Organization: {org_name} ({org_id})")
                    else:
                        print("⚠️ No organization found. Creating 'Default Organization'...")
                        org_id = str(uuid.uuid4())
                        org_name = "Default Organization"
                        
                        # Simple insert based on standard schema
                        cur.execute("""
                            INSERT INTO organizations 
                            (id, name, type, subscription_plan, amazon_account_limit, seat_price, status)
                            VALUES (%s, %s, 'AGENCY', 'ENTERPRISE', 10, 0, 'ACTIVE')
                        """, (org_id, org_name))
                        conn.commit()
                        print(f"✅ Created Organization: {org_name} ({org_id})")
                except psycopg2.Error as e:
                    print(f"❌ Failed to query/create organization in Postgres: {e}")
                    return
        
        if not org_id:
            print("❌ Could not determine Organization ID. Aborting.")
            return

        # 2. Update Postgres Data (if used via PostgresManager for APP DATA)
        # Accounts might exist in Postgres "accounts" table too
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
             print("\nUpdating Postgres Application Accounts...")
             try:
                 pg_conn = psycopg2.connect(db_url)
                 pg_cur = pg_conn.cursor()
                 
                 # Check if accounts table exists and update
                 try:
                     pg_cur.execute("UPDATE accounts SET organization_id = %s WHERE organization_id IS NULL", (org_id,))
                     pg_count = pg_cur.rowcount
                     pg_conn.commit()
                     print(f"   Updated {pg_count} accounts in Postgres")
                 except psycopg2.errors.UndefinedColumn:
                     pg_conn.rollback()
                     print("   Column missing. Migrating Postgres table...")
                     pg_cur.execute("ALTER TABLE accounts ADD COLUMN organization_id TEXT")
                     pg_conn.commit()
                     print("   ✅ Added organization_id column to accounts")
                     
                     # Retry update
                     pg_cur.execute("UPDATE accounts SET organization_id = %s WHERE organization_id IS NULL", (org_id,))
                     pg_count = pg_cur.rowcount
                     pg_conn.commit()
                     print(f"   Updated {pg_count} accounts in Postgres")
                 except psycopg2.Error as pge:
                     # Table might not exist or other error
                     pg_conn.rollback()
                     print(f"   Skipped Postgres update (Table might not exist): {pge}")

                     
                 pg_conn.close()
             except Exception as e:
                 print(f"   Skipped Postgres update (Connection error): {e}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
