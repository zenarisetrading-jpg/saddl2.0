"""
Platform Service Module
======================
Handles Super Admin operations that span across organizations.
This service is restricted to users with direct platform management privileges.
"""

import uuid
import logging
from typing import List, Optional, NamedTuple
from datetime import datetime

from app_core.db_manager import get_db_manager
from app_core.auth.invitation_service import InvitationService, InvitationResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrganizationSummary(NamedTuple):
    id: str
    name: str
    admin_count: int
    user_count: int
    created_at: datetime
    status: str

class OrganizationResult(NamedTuple):
    success: bool
    message: str
    organization_id: Optional[str] = None
    invitation_result: Optional[InvitationResult] = None

class PlatformService:
    def __init__(self):
        self.db = get_db_manager()
        self.invitation_service = InvitationService()
        
    def list_organizations(self) -> List[OrganizationSummary]:
        """
        List all organizations with summary metrics.
        Returns ordered by creation date (newest first).
        """
        orgs = []
        try:
            with self.db._get_connection() as conn:
                cur = conn.cursor()
                try:
                    # Query organizations with user counts
                    cur.execute("""
                        SELECT 
                            o.id,
                            o.name,
                            o.created_at,
                            o.status,
                            COUNT(u.id) as total_users,
                            COUNT(CASE WHEN u.role IN ('ADMIN', 'OWNER') THEN 1 END) as admin_users
                        FROM organizations o
                        LEFT JOIN users u ON o.id::text = u.organization_id
                        GROUP BY o.id, o.name, o.created_at, o.status
                        ORDER BY o.created_at DESC
                    """)
                    
                    rows = cur.fetchall()
                    for row in rows:
                        org_id, name, created_at, status, total_users, admin_users = row
                        orgs.append(OrganizationSummary(
                            id=str(org_id),
                            name=name,
                            admin_count=admin_users,
                            user_count=total_users,
                            created_at=created_at,
                            status=status or 'ACTIVE'
                        ))
                finally:
                    cur.close()
        except Exception as e:
            logger.error(f"Error listing organizations: {e}")
            import streamlit as st
            st.warning(f"Complex query failed: {str(e)}. Attempting fallback...")
            
            # Fallback to simple query without user counts
            try:
                with self.db._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id, name, created_at, status FROM organizations ORDER BY created_at DESC")
                        rows = cur.fetchall()
                        for row in rows:
                             # Handle tuple unpacking based on cursor type (RealDict vs tuple)
                            if isinstance(row, tuple):
                                org_id, name, created_at, status = row
                            else:
                                org_id = row['id']
                                name = row['name']
                                created_at = row['created_at']
                                status = row['status']
                                
                            orgs.append(OrganizationSummary(
                                id=str(org_id),
                                name=name,
                                admin_count=0,
                                user_count=0,
                                created_at=created_at,
                                status=status or 'ACTIVE'
                            ))
            except Exception as e2:
                st.error(f"Critical DB Error: {str(e2)}")

        return orgs

    def create_organization(
        self, 
        name: str, 
        admin_email: str,
        creator_user_id: Optional[str] = None
    ) -> OrganizationResult:
        """
        Create a new organization and invite its first admin (Owner).
        """
        if not name or not name.strip():
            return OrganizationResult(False, "Organization name is required")
            
        if not admin_email or "@" not in admin_email:
            return OrganizationResult(False, "Valid admin email is required")

        org_id = str(uuid.uuid4())
        
        # 1. Create Organization Record
        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    # Check for duplicate name
                    cur.execute("SELECT id FROM organizations WHERE name = %s", (name,))
                    if cur.fetchone():
                        return OrganizationResult(False, f"Organization '{name}' already exists")
                    
                    # Create Org
                    cur.execute("""
                        INSERT INTO organizations (
                            id, name, type, subscription_plan, 
                            amazon_account_limit, seat_price, status
                        )
                        VALUES (%s, %s, 'SELLER', 'PROFESSIONAL', 1, 49.00, 'ACTIVE')
                    """, (org_id, name))
                    
        except Exception as e:
            logger.error(f"Error creating organization: {e}")
            return OrganizationResult(False, f"Database error: {str(e)}")

        # 2. Invite Admin User
        # We try to use a real user ID if provided, otherwise check for super admin, else None (invites table allows null for system invites if adjusted, but for now we follow code)
        inviter_id = creator_user_id
        
        # If no creator specified, try to find default admin to attribute the invite to
        if not inviter_id:
            try:
                with self.db._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM users WHERE email = 'admin@saddl.io'")
                        res = cur.fetchone()
                        if res:
                            inviter_id = str(res[0])
            except Exception:
                pass
        
        # Invite as OWNER
        invite_result = self.invitation_service.create_invitation(
            email=admin_email,
            organization_id=org_id,
            invited_by_user_id=inviter_id if inviter_id else str(uuid.uuid4()), # Fallback UUID if absolutely necessary to pass non-null constraint, though ideally we have a real user
            role="OWNER",
            inviter_name="SADDL Admin",
            inviter_org_name="SADDL AdPulse"
        )
        
        if invite_result.success:
            return OrganizationResult(
                success=True, 
                message=f"Created organization '{name}' and invited {admin_email}",
                organization_id=org_id,
                invitation_result=invite_result
            )
        else:
            return OrganizationResult(
                success=True, # Org created successfully, but invite failed
                message=f"Created organization '{name}' but invite failed: {invite_result.message}",
                organization_id=org_id,
                invitation_result=invite_result
            )
