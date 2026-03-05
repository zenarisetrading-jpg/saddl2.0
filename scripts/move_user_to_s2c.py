
"""
Move User to S2C-Test Organization
==================================
Moves 'thasbihak@zenarise.org' to the 'S2C-Test' organization (ID: 6462e051...).
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

# Configuration
TARGET_ORG_ID = "6462e051-9fbd-5009-8461-d61427f1e707" # S2C-Test (from previous migration)
TARGET_EMAIL = "thasbihak@zenarise.org"

def move_user():
    print(f"USER MOVE: Moving {TARGET_EMAIL} to S2C-Test...")
    
    # Force load .env
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
    
    db = get_db_manager()
    ph = db.placeholder
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Check current status
        cursor.execute(f"SELECT organization_id, role FROM users WHERE email = {ph}", (TARGET_EMAIL,))
        row = cursor.fetchone()
        
        if not row:
            print(f"USER MOVE: ❌ User {TARGET_EMAIL} not found!")
            return
            
        current_org, role = row
        print(f"USER MOVE: Current Org: {current_org} | Role: {role}")
        
        if str(current_org) == TARGET_ORG_ID:
            print("USER MOVE: User is already in S2C-Test.")
            return

        # 2. Update Org ID
        print(f"USER MOVE: Updating to {TARGET_ORG_ID}...")
        cursor.execute(f"""
            UPDATE users 
            SET organization_id = {ph} 
            WHERE email = {ph}
        """, (TARGET_ORG_ID, TARGET_EMAIL))
        
        if cursor.rowcount > 0:
            print(f"USER MOVE: ✅ Success! {TARGET_EMAIL} is now in S2C-Test.")
        else:
            print("USER MOVE: ⚠️ Update failed (no rows affected).")

if __name__ == "__main__":
    move_user()
