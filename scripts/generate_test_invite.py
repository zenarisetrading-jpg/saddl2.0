
import sys
import os
import uuid
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv('desktop/.env')

from app_core.auth.invitation_service import InvitationService

def main():
    print("🚀 SADDL AdPulse - Invitation Generator")
    
    email = input("Enter email to invite (e.g. test@saddl.io): ")
    if not email:
        print("❌ Email required")
        return

    # Initialize service first
    service = InvitationService()
    
    # Prompt for Organization mode
    print("\nSelect Organization Mode:")
    print("1. Join Existing Organization (Default - sees existing data)")
    print("2. Create NEW Organization (Simulate fresh signup - empty state)")
    mode = input("Choice [1/2]: ").strip()
    
    mode = input("Choice [1/2]: ").strip()
    
    conn = None
    try:
        # Use context manager pattern
        with service._get_connection() as conn:
            cur = conn.cursor()
            
            org_id = None
            org_name = None
            
            if mode == "2":
                # CREATE NEW ORG
                org_name = input("Enter new Organization Name (e.g. 'Test Agency'): ").strip() or "Test Agency"
                org_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO organizations (id, name, type, subscription_plan, amazon_account_limit, seat_price, status)
                    VALUES (%s, %s, 'AGENCY', 'ENTERPRISE', 10, 0, 'ACTIVE')
                """, (org_id, org_name))
                # context manager will commit on exit
                print(f"✅ Created New Organization: {org_name} ({org_id})")
                
            else:
                # JOIN EXISTING
                cur.execute("SELECT id, name FROM organizations LIMIT 1")
                org_row = cur.fetchone()
                
                if not org_row:
                    print("❌ No organizations found. Creating default.")
                    org_name = "Default Org"
                    org_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO organizations (id, name, type, subscription_plan, amazon_account_limit, seat_price, status)
                        VALUES (%s, %s, 'AGENCY', 'ENTERPRISE', 10, 0, 'ACTIVE')
                    """, (org_id, org_name))
                    # context manager will commit on exit
                else:
                    org_id = str(org_row[0])
                    org_name = org_row[1]
                    
                print(f"Using Organization: {org_name} ({org_id})")

            # Get first user to act as inviter
            try:
                cur.execute("SELECT id, email FROM users LIMIT 1")
                user_row = cur.fetchone()
            except Exception:
                user_row = None
                
            if user_row:
                admin_id = str(user_row[0])
                inviter_name = user_row[1]
                print(f"Using Inviter: {inviter_name} ({admin_id})")
            else:
                print("⚠️ Could not find a user to act as inviter. Using dummy ID.")
                admin_id = "00000000-0000-0000-0000-000000000000"
                inviter_name = "System Admin"
            
            # Cursor closes automatically or we can ensure it
            cur.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        # Only show traceback if needed for deeper debugging
        # import traceback
        # traceback.print_exc()
        return
    
    # Create invitation
    result = service.create_invitation(
        email=email,
        organization_id=org_id,
        invited_by_user_id=admin_id,
        role="OPERATOR",
        inviter_name=inviter_name,
        inviter_org_name=org_name
    )
    
    if result.success:
        print("\n✅ Invitation Created Successfully!")
        print(f"Token: {result.invitation.token}")
        print(f"\n🔗 ACCEPTANCE LINK:\nhttp://localhost:8501/accept-invite?token={result.invitation.token}")
        print("\nClick this link to start the Onboarding flow as a new user.")
    else:
        print(f"\n❌ Error: {result.message}")

if __name__ == "__main__":
    main()
