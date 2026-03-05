import os
import sys
import uuid
import logging
from datetime import datetime

# Add desktop to path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
desktop_dir = os.path.dirname(current_dir)
sys.path.insert(0, desktop_dir)

# Load env vars
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(desktop_dir, '.env'))
    load_dotenv(os.path.join(os.path.dirname(desktop_dir), '.env'))
except ImportError:
    pass

from app_core.auth.invitation_service import InvitationService
from app_core.postgres_manager import PostgresManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def onboard_client():
    print("="*60)
    print("SADDL AdPulse - New Client Onboarding")
    print("="*60)
    
    # 1. Gather Info
    org_name = input("\nEnter New Organization Name: ").strip()
    if not org_name:
        print("Organization name is required.")
        return

    admin_email = input("Enter Client Admin Email: ").strip()
    if not admin_email or "@" not in admin_email:
        print("Valid email is required.")
        return

    # 2. Confirm
    print(f"\n[CONFIRMATION]")
    print(f"Organization: {org_name}")
    print(f"Admin Email:  {admin_email}")
    confirm = input("\nProceed? (y/n): ").lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    # 3. Create Organization
    print("\nCreating Organization...")
    db = PostgresManager()
    
    org_id = str(uuid.uuid4())
    
    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                # Check if exists
                cur.execute("SELECT id FROM organizations WHERE name = %s", (org_name,))
                existing = cur.fetchone()
                if existing:
                    print(f"Organization '{org_name}' already exists! ID: {existing[0]}")
                    org_id = str(existing[0])
                else:
                    cur.execute("""
                        INSERT INTO organizations (
                            id, name, type, subscription_plan, 
                            amazon_account_limit, seat_price, status
                        )
                        VALUES (%s, %s, 'SELLER', 'PROFESSIONAL', 1, 49.00, 'ACTIVE')
                        RETURNING id
                    """, (org_id, org_name))
                    print(f"Organization created with ID: {org_id}")
    except Exception as e:
        print(f"Database Error: {e}")
        return

    # 4. Send Invitation
    print("\nSending Invitation...")
    service = InvitationService()
    
    # We invite them as OWNER of the new org
    # The 'invited_by' will be marked as 'system' or the admin running this (we'll use specific UUID or None)
    # Since invited_by_user_id is a UUID foreign key, we ideally need a valid user ID. 
    # We'll try to find the current admin user (admin@saddl.io) to use as the inviter.
    
    inviter_id = None
    inviter_name = "SADDL Admin"
    
    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = 'admin@saddl.io'")
                res = cur.fetchone()
                if res:
                    inviter_id = str(res[0])
    except Exception:
        pass
        
    if not inviter_id:
        print("Warning: Could not find admin@saddl.io to use as inviter. Using a placeholder UUID (might fail FK constraint if strict).")
        # If strict FK, this script might fail if we don't have a valid user. 
        # But we previously seeded admin@saddl.io, so it should exist.
        return

    result = service.create_invitation(
        email=admin_email,
        organization_id=org_id,
        invited_by_user_id=inviter_id,
        role="OWNER",
        inviter_name=inviter_name,
        inviter_org_name="SADDL AdPulse"
    )

    if result.success:
        print(f"\nSUCCESS! Invitation sent to {admin_email}")
        if result.invitation:
             # Print the link just in case email fails
             # Construct URL manually since we can't easily get it from the service return object method (it returns a Result namedTuple)
             # But the service uses _get_app_url internally. 
             # We can use the service's internal helper if we wanted, but let's just assume standard format.
             print(f"Link (if email fails): {service._get_app_url().rstrip('/')}/?token={result.invitation.token}")
    else:
        print(f"\nFAILED to send invitation: {result.message}")

if __name__ == "__main__":
    onboard_client()
