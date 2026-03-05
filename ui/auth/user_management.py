"""
User Management UI
==================
Screen for managing users, roles, and invites.
PRD Reference: ORG_USERS_ROLES_PRD.md §11, §13

Features:
- List users
- Invite user (with billing warning)
- Role assignment
- Email invitations (Phase 1 - feature flagged)
"""

import streamlit as st
import os
from app_core.auth.permissions import Role, PERMISSION_MATRIX, get_billable_default, can_manage_role, has_permission
from app_core.auth.middleware import require_permission
from config.features import FEATURE_EMAIL_INVITATIONS, FeatureFlags

# Example price (could come from config/DB)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_users_cached(org_id: str):
    """Cache user list query - prevents repeated DB calls."""
    from app_core.auth.service import AuthService
    auth = AuthService()
    return auth.list_users(org_id)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_org_accounts_cached(org_id: str):
    """Cache organization accounts query for user management."""
    import streamlit as st
    db = st.session_state.get('db_manager')
    if not db:
        return []

    accounts_query = "SELECT id, display_name, marketplace FROM amazon_accounts WHERE organization_id = %s ORDER BY display_name"

    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(accounts_query, (org_id,))
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception:
        return []


def render_user_management():
    st.header("User Management")

    # NUCLEAR CSS OVERRIDE - Dark Vine Theme
    st.markdown("""
    <style>
    /* Force Dark Vine on ALL primary buttons */
    button[kind="primary"],
    button[data-testid="baseButton-primary"],
    div[data-testid="stForm"] button[kind="primary"] {
        background: linear-gradient(135deg, #464156 0%, #2E2A36 100%) !important;
        color: #E9EAF0 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }
    button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #5B5670 0%, #464156 100%) !important;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* Dark Vine Alert/Warning Ribbons */
    div[data-testid="stAlert"] {
        background-color: rgba(46, 42, 54, 0.95) !important;
        border: 1px solid rgba(154, 154, 170, 0.2) !important;
        color: #E9EAF0 !important;
    }
    div[data-testid="stAlert"] * {
        color: #E9EAF0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # V2 Backend Wiring
    from app_core.auth.service import AuthService

    # Get current user (AuthService is already initialized in main, so this is fast)
    auth = AuthService()
    current_user = auth.get_current_user()
    
    # 0. Page Access Guard
    if not current_user or not has_permission(current_user.role, 'manage_users'):
        st.error("⛔ Access Denied: Administrator privileges required.")
        return
    
    # 1. User List (Real Data)
    st.subheader("Team Members")
    
    
    # helper for Phase 3.5 UI
    def render_account_override_editor(user):
        """Show per-account access restrictions for a user."""
        st.write("---")
        st.subheader(f"Account Permissions: {user['email']}")
        st.caption(f"Global Role: **{user['role']}** · Overrides can only reduce access, never increase it")
        
        # Get all org accounts (cached to avoid slow queries)
        accounts = _fetch_org_accounts_cached(str(current_user.organization_id))

        if not accounts:
            st.info("No accounts in this organization.")
            return

        for acc in accounts:
            col_a, col_b, col_c = st.columns([3, 2, 1])
            with col_a:
                st.write(f"**{acc['display_name']}** ({acc['marketplace']})")
            
            with col_b:
                # Get current override role
                # Since auth.list_users doesn't return overrides, we fetch it or pass full user obj
                # Optimization: We should probably fetch overrides for specific user on demand
                # For now, let's just query it directly to be safe and simple
                current_ov_role = "DEFAULT"
                try: 
                    # This is N+1 query pattern but OK for admin UI with < 50 accounts
                    ov_res = db.fetch_one(
                        "SELECT role FROM user_account_overrides WHERE user_id = %s AND amazon_account_id = %s",
                        (str(user['id']), str(acc['id']))
                    )
                    if ov_res:
                        current_ov_role = ov_res['role']
                except Exception:
                    pass

                # Available options (Phase 3.5: Downgrade Only)
                # If Global is ADMIN/OPERATOR -> Can enable VIEWER
                # If Global is ADMIN -> Can enable OPERATOR
                
                # Logic:
                # 1. Start with DEFAULT
                options = ["DEFAULT"]
                
                user_role_str = user['role']
                
                # If global is > VIEWER, can restrict to VIEWER
                if user_role_str in ['OWNER', 'ADMIN', 'OPERATOR']:
                    options.append("VIEWER")
                    
                # If global is > OPERATOR, can restrict to OPERATOR
                if user_role_str in ['OWNER', 'ADMIN']:
                     options.append("OPERATOR")
                     
                safe_index = 0
                if current_ov_role in options:
                    safe_index = options.index(current_ov_role)
                
                selected_role = st.selectbox(
                    "Access Level",
                    options=options,
                    index=safe_index,
                    key=f"ov_{user['id']}_{acc['id']}",
                    label_visibility="collapsed"
                )

            with col_c:
                if st.button("Save", key=f"save_{user['id']}_{acc['id']}", type="secondary"):
                    if selected_role == "DEFAULT":
                        res = auth.remove_account_override(str(user['id']), str(acc['id']))
                    else:
                        res = auth.set_account_override(
                            str(user['id']), 
                            str(acc['id']), 
                            Role(selected_role),
                            str(current_user.id)
                        )
                    
                    if res["success"]:
                        st.success("Saved")
                        st.rerun()
                    else:
                        st.error(res.get("error"))

    if current_user:
        users = _fetch_users_cached(str(current_user.organization_id))
        if not users:
             st.info("No users found (except you?)")
             
        for user in users:
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(user["email"])
                if user["id"] == current_user.id:
                    st.caption("(You)")
            with col2:
                st.code(user["role"])
            with col3:
                st.caption(user["status"])
                
                # Check strict hierarchy: Can I manage this user?
                # User Role usually comes as string from list_users
                can_edit = can_manage_role(current_user.role.value, user["role"])
                
                # Admin Reset Action
                if user["id"] != current_user.id and can_edit:
                    # Unique key needed for button inside loop
                    if st.button("Reset Pwd", key=f"reset_{user['id']}", help="Force reset user password", type="primary"):
                        res = auth.admin_reset_password(current_user, str(user["id"]))
                        if res.success:
                            st.warning(f"⚠️ Temp Password for {user['email']}: {res.reason}")
                            st.info("User will be forced to change this on next login.")
                        else:
                            st.error(res.reason)
                        
                # Phase 3.5: Account Access Overrides (Expandable)
                # Only show if I can manage them
                if user['id'] != current_user.id and can_edit:
                    with st.expander("Manage Account Access"):
                        render_account_override_editor(user)
    else:
        st.error("Session error.")
            
    st.divider()

    # 2. Invite User
    st.subheader("Invite New User")

    # Check if email invitations are enabled
    if FEATURE_EMAIL_INVITATIONS:
        # =====================================================================
        # NEW EMAIL INVITATION FLOW (Phase 1)
        # =====================================================================
        _render_email_invitation_form(auth, current_user)

        # Legacy fallback in expander
        with st.expander("Manual User Creation (Legacy)", expanded=False):
            st.warning(
                "This is the legacy method. Use email invitations above for better user experience. "
                "Manual creation requires you to securely share the temporary password with the user."
            )
            _render_legacy_invite_form(auth, current_user)
    else:
        # =====================================================================
        # LEGACY FLOW (Feature flag disabled)
        # =====================================================================
        _render_legacy_invite_form(auth, current_user)

        # Show info about email invitations
        st.info(
            "Email invitations are available but not enabled. "
            "Set `ENABLE_EMAIL_INVITATIONS=true` in your .env file to enable."
        )

    # =========================================================================
    # PENDING INVITATIONS LIST (Only show if email invitations enabled)
    # =========================================================================
    if FEATURE_EMAIL_INVITATIONS:
        _render_pending_invitations(auth, current_user)


def _render_email_invitation_form(auth, current_user):
    """
    Render the new email invitation form.
    Sends invitation email with secure link instead of showing temp password.
    """
    from app_core.auth.invitation_service import InvitationService

    # Check SMTP configuration
    smtp_configured = all([
        os.environ.get("SMTP_HOST"),
        os.environ.get("SMTP_USER"),
        os.environ.get("SMTP_PASSWORD")
    ])

    if not smtp_configured:
        st.error(
            "Email invitations require SMTP configuration. "
            "Please set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in your .env file."
        )
        st.info("Falling back to manual user creation below.")
        _render_legacy_invite_form(auth, current_user)
        return

    # Get organization name for the email
    org_name = _get_organization_name(current_user.organization_id)
    inviter_name = current_user.email.split('@')[0].title()  # Simple name extraction

    with st.form("email_invite_form", clear_on_submit=True):
        new_email = st.text_input(
            "Email Address",
            placeholder="colleague@company.com",
            help="The user will receive an email with a secure link to set up their account."
        )

        new_role_str = st.selectbox(
            "Role",
            options=[r.value for r in Role],
            index=2,  # Default to OPERATOR
            help="Select the role this user will have in your organization."
        )



        submitted = st.form_submit_button("Send Invitation", type="primary")

        if submitted:
            if not new_email:
                st.error("Email address is required.")
            elif "@" not in new_email:
                st.error("Please enter a valid email address.")
            else:
                # Use the new InvitationService
                invitation_service = InvitationService()

                result = invitation_service.create_invitation(
                    email=new_email,
                    organization_id=str(current_user.organization_id),
                    invited_by_user_id=str(current_user.id),
                    role=new_role_str,
                    inviter_name=inviter_name,
                    inviter_org_name=org_name
                )

                if result.success:
                    if result.error_code == "EMAIL_FAILED":
                        # Invitation created but email failed
                        st.warning(f"Invitation created for {new_email}, but the email could not be sent.")
                        st.info("You can resend the invitation from the pending invitations list below.")
                    else:
                        st.success(f"Invitation sent to {new_email}")
                        st.info("They will receive an email with a secure link to set up their account.")
                        st.balloons()
                else:
                    st.error(f"Failed to send invitation: {result.message}")


def _render_legacy_invite_form(auth, current_user):
    """
    Render the legacy invite form with temporary password display.
    Kept for backwards compatibility and as fallback.
    """
    with st.form("legacy_invite_form"):
        new_email = st.text_input("Email Address")
        new_role_str = st.selectbox(
            "Role",
            options=[r.value for r in Role],
            index=2,  # Default to OPERATOR
            key="legacy_role_select"
        )



        submitted = st.form_submit_button("Create User", type="primary")

        if submitted:
            if not new_email:
                st.error("Email required")
            else:
                if current_user:
                    res = auth.create_user_invite(new_email, Role(new_role_str), current_user.organization_id)
                    if res["success"]:
                        st.success(f"User created: {new_email}")
                        st.info(f"Temporary Password: **{res.get('temp_password', 'Welcome123!')}**")
                        st.caption("Please securely share this password with the user. They will be required to change it on first login.")
                        st.balloons()
                    else:
                        st.error(f"Failed: {res.get('error')}")
                else:
                    st.error("You must be logged in.")


def _render_pending_invitations(auth, current_user):
    """
    Render the list of pending invitations with resend/revoke options.
    """
    from app_core.auth.invitation_service import InvitationService

    st.divider()
    st.subheader("Pending Invitations")

    invitation_service = InvitationService()

    try:
        invitations = invitation_service.list_invitations(
            organization_id=str(current_user.organization_id),
            status_filter="pending"
        )
    except Exception as e:
        st.error(f"Could not load invitations: {e}")
        return

    if not invitations:
        st.info("No pending invitations.")
        return

    # Get organization name for resend
    org_name = _get_organization_name(current_user.organization_id)
    inviter_name = current_user.email.split('@')[0].title()

    for inv in invitations:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

        with col1:
            st.write(inv.email)
            # Show time remaining
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if inv.expires_at > now:
                hours_left = (inv.expires_at - now).total_seconds() / 3600
                if hours_left > 24:
                    st.caption(f"Expires in {int(hours_left / 24)} days")
                else:
                    st.caption(f"Expires in {int(hours_left)} hours")
            else:
                st.caption("Expired", help="This invitation has expired")

        with col2:
            st.code(inv.role)

        with col3:
            if st.button("Resend", key=f"resend_{inv.id}", type="secondary"):
                result = invitation_service.resend_invitation(
                    invitation_id=inv.id,
                    inviter_name=inviter_name,
                    inviter_org_name=org_name
                )
                if result.success:
                    st.success("Invitation resent!")
                    st.rerun()
                else:
                    st.error(result.message)

        with col4:
            if st.button("Revoke", key=f"revoke_{inv.id}", type="secondary"):
                result = invitation_service.revoke_invitation(
                    invitation_id=inv.id,
                    revoked_by_user_id=str(current_user.id)
                )
                if result.success:
                    st.success("Invitation revoked.")
                    st.rerun()
                else:
                    st.error(result.message)


def _get_organization_name(organization_id) -> str:
    """
    Get the organization name from the database.
    Returns a default if not found.
    """
    try:
        from app_core.auth.service import AuthService
        auth = AuthService()
        with auth._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM organizations WHERE id = %s", (str(organization_id),))
                row = cur.fetchone()
                if row:
                    return row[0]
    except Exception:
        pass
    return "your organization"
