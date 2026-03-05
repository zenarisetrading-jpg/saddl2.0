
"""
Create S2C Admin User
=====================
Creates a user 's2c_admin@saddle.io' linked to the 'S2C-Test' organization.
"""

import os
import sys
import uuid
from pathlib import Path

# Add desktop to path
desktop_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if desktop_path not in sys.path:
    sys.path.insert(0, desktop_path)

from app_core.auth.service import AuthService
from app_core.db_manager import get_db_manager

# Configuration
TARGET_ORG_ID = "6462e051-9fbd-5009-8461-d61427f1e707" # S2C-Test
NEW_USER_EMAIL = "s2c_admin@saddle.io"
NEW_USER_PASSWORD = "Welcome123!" # Default

def create_user():
    print("USER SETUP: Creating S2C Admin user...")
    
    # Force load .env
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
    
    auth = AuthService()
    
    # Check if user exists directly via DB
    db = auth.db_manager
    ph = db.placeholder
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, organization_id, email FROM users WHERE email = {ph}", (NEW_USER_EMAIL,))
        existing_row = cursor.fetchone()
    
    if existing_row:
        user_id, existing_org_id, _ = existing_row
        print(f"USER SETUP: User {NEW_USER_EMAIL} already exists.")
        
        if str(existing_org_id) != TARGET_ORG_ID:
             print(f"USER SETUP: ⚠️ User exists but in wrong Org ({existing_org_id}). Moving...")
             # Move user
             with db._get_connection() as conn:
                 cursor = conn.cursor()
                 cursor.execute(f"UPDATE users SET organization_id = {ph} WHERE email = {ph}", (TARGET_ORG_ID, NEW_USER_EMAIL))
                 print("USER SETUP: ✅ User moved to S2C-Test.")
        else:
             print("USER SETUP: User is already in S2C-Test.")
             
    else:
        print(f"USER SETUP: Creating new user {NEW_USER_EMAIL}...")
        # We can't use auth.sign_up usually without an invitation or open signups.
        # But we can use internal methods or direct DB execution.
        # Let's use `auth.create_user` (if it exists) or direct insert.
        # checking auth service... create_user_invite does it? No that makes pending.
        # We'll use the seeding logic equivalent: direct insert.
        
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash(NEW_USER_PASSWORD)
        
        db = auth.db_manager
        ph = db.placeholder
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Using UUID for user ID
            user_id = str(uuid.uuid4())
            
            cursor.execute(f"""
                INSERT INTO users (id, organization_id, email, password_hash, role, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, 'ADMIN', 'ACTIVE')
            """, (user_id, TARGET_ORG_ID, NEW_USER_EMAIL, pwd_hash))
            
            print(f"USER SETUP: ✅ Created user {NEW_USER_EMAIL} (ID: {user_id})")
            print(f"USER SETUP: Password set to: {NEW_USER_PASSWORD}")

if __name__ == "__main__":
    create_user()
