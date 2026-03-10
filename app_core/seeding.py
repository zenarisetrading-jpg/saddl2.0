"""
Database Seeding Module
=======================
Handles initialization of default data (e.g., admin user) for fresh deployments.
This is critical for Streamlit Cloud where the SQLite DB is ephemeral.
"""

import os
import uuid
from app_core.auth.service import AuthService
from app_core.auth.models import Role

def seed_initial_data():
    """
    Check if users exist. If not, create default admin.
    Optimized to use a single connection and exit early if already seeded.
    """
    email = os.environ.get('SADDL_BOOTSTRAP_EMAIL')
    password = os.environ.get('SADDL_BOOTSTRAP_PASSWORD')
    if not email or not password:
        raise RuntimeError('SADDL_BOOTSTRAP_EMAIL and SADDL_BOOTSTRAP_PASSWORD must be set before first run')

    print("SEED: Initializing...")

    try:
        auth_service = AuthService()
        print("SEED: AuthService created")
    except Exception as e:
        print(f"SEED: Failed to create AuthService: {e}")
        return f"AuthService creation failed: {e}"

    default_org_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "saddle.io"))
    default_org_name = "Primary Organization"

    try:
        print("SEED: Attempting DB connection...")
        # Use single connection for all operations
        with auth_service._get_connection() as conn:
            print("SEED: Connection established")
            cur = conn.cursor()
            ph = auth_service.db_manager.placeholder

            # 1. Quick check if admin exists (early exit for most startups)
            print(f"SEED: Checking if admin exists ({email})...")
            cur.execute(f"SELECT id FROM users WHERE email = {ph}", (email,))
            if cur.fetchone():
                print("SEED: Admin exists, skipping.")
                return "SEED: Admin exists, skipping."

            # 2. Ensure organization exists (UPSERT)
            print("SEED: Creating organization...")
            try:
                cur.execute(f"""
                    INSERT INTO organizations (id, name, type) VALUES ({ph}, {ph}, 'SELLER')
                    ON CONFLICT (id) DO NOTHING
                """, (default_org_id, default_org_name))
                conn.commit()
                print("SEED: Organization created")
            except Exception as org_err:
                print(f"SEED WARNING: Organization seed failed: {org_err}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"SEED CHECK ERROR: {e}")
        return f"Error checking DB: {e}"

    # 3. Create admin (only if we got here)
    print("SEED: Creating default admin...")
    try:
        success = auth_service.create_user_manual(
            email=email,
            password=password,
            role=Role.ADMIN,
            org_id=default_org_id
        )

        if success:
            msg = f"SEED: Created admin: {email}"
            print(msg)
            return msg
        else:
            print("SEED: Failed to create admin (Internal Error).")
            return "SEED: Failed to create admin (Internal Error)."
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = f"SEED ERROR: {e}"
        print(msg)
        return msg
