"""
Invitation Acceptance Page
==========================
Page where invited users set up their account after clicking the email link.

PRD Reference: Automated User Onboarding Implementation Plan - Phase 2

Flow:
1. User clicks invitation link with token
2. Token is validated
3. User fills out account setup form (name, password)
4. Account is created with role from invitation
5. Invitation is marked as accepted
6. User is auto-logged in
7. User is redirected to onboarding wizard (if enabled)

URL: /accept-invite?token=<secure_token>
"""

import streamlit as st
import re
from typing import Optional, Tuple

from app_core.auth.invitation_service import InvitationService, Invitation
from app_core.auth.service import AuthService
from app_core.auth.hashing import hash_password
from app_core.auth.permissions import Role, get_billable_default
from config.features import FEATURE_ONBOARDING_WIZARD
from config.design_system import COLORS, TYPOGRAPHY, SPACING, GLASSMORPHIC


def get_invitation_token() -> Optional[str]:
    """
    Extract the invitation token from URL query parameters.

    Returns:
        Token string if present, None otherwise
    """
    try:
        params = st.query_params
        return params.get("token")
    except Exception:
        return None


def validate_password(password: str, confirm_password: str) -> Tuple[bool, list]:
    """
    Validate password meets requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - Passwords must match

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters")

    if not re.search(r'[A-Z]', password):
        errors.append("Password must include at least one uppercase letter")

    if not re.search(r'[a-z]', password):
        errors.append("Password must include at least one lowercase letter")

    if not re.search(r'[0-9]', password):
        errors.append("Password must include at least one number")

    if password != confirm_password:
        errors.append("Passwords do not match")

    return (len(errors) == 0, errors)


def create_user_from_invitation(
    invitation: Invitation,
    first_name: str,
    last_name: str,
    password: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Create a new user account from an invitation.

    Args:
        invitation: The validated invitation object
        first_name: User's first name
        last_name: User's last name
        password: User's chosen password

    Returns:
        Tuple of (success, user_id, error_message)
    """
    try:
        auth = AuthService()
        # Use context manager for connection pooling
        with auth._get_connection() as conn:
            with conn.cursor() as cur:
                # Check if user already exists
                cur.execute("SELECT id FROM users WHERE email = %s", (invitation.email,))
                if cur.fetchone():
                    return (False, None, "An account with this email already exists")

                # Hash password
                password_hash = hash_password(password)

                # Determine billable status based on role
                billable = get_billable_default(invitation.role)

                # Create user
                cur.execute("""
                    INSERT INTO users (
                        email, password_hash, role, organization_id,
                        billable, status, must_reset_password
                    )
                    VALUES (%s, %s, %s, %s, %s, 'ACTIVE', FALSE)
                    RETURNING id
                """, (
                    invitation.email,
                    password_hash,
                    invitation.role,
                    invitation.organization_id,
                    billable
                ))

                result = cur.fetchone()
                user_id = str(result[0])
                
                # Connection is committed automatically by the context manager upon exit
                
        return (True, user_id, None)

    except Exception as e:
        return (False, None, str(e))


def render_accept_invite():
    """
    Render the invitation acceptance page.

    This page handles:
    - Token validation
    - Account setup form
    - User creation
    - Auto-login
    """
    # Apply consistent styling
    _apply_page_styles()

    # Get token from URL
    token = get_invitation_token()

    if not token:
        _render_error_state(
            "Invalid Invitation Link",
            "This invitation link appears to be invalid or incomplete. "
            "Please check the link in your email and try again.",
            show_login_link=True
        )
        return

    # Validate token
    invitation_service = InvitationService()
    invitation = invitation_service.validate_token(token)

    if not invitation:
        _render_error_state(
            "Invitation Expired or Invalid",
            "This invitation has expired, already been used, or is invalid. "
            "Please contact your administrator to receive a new invitation.",
            show_login_link=True
        )
        return

    # Token is valid - show account setup form
    _render_account_setup_form(invitation, token)


def _apply_page_styles():
    """Apply glassmorphic styling to the page."""
    st.markdown(f"""
        <style>
        /* Page background */
        .stApp {{
            background: {COLORS['background']};
        }}

        /* Centered container */
        .block-container {{
            max-width: 550px;
            padding-top: 2rem;
            padding-bottom: 5rem;
        }}

        /* Header styling */
        h1.invite-title {{
            font-family: {TYPOGRAPHY['font_family']};
            font-weight: 700;
            font-size: 2rem;
            text-align: center;
            margin-top: 0;
            margin-bottom: 0.5rem;
            color: {COLORS['text_primary']};
        }}

        div.invite-subtitle {{
            text-align: center;
            color: {COLORS['text_secondary']};
            margin-bottom: 1.5rem;
            font-size: 1rem;
        }}

        /* Form container */
        div[data-testid="stForm"] {{
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            padding: 2rem;
            border-radius: {GLASSMORPHIC['border_radius']};
        }}

        /* Input fields */
        .stTextInput input {{
            background: {GLASSMORPHIC['background']} !important;
            border: {GLASSMORPHIC['border']} !important;
            border-radius: 12px !important;
            color: {COLORS['text_primary']} !important;
            padding: 12px 16px !important;
        }}

        .stTextInput input:focus {{
            border-color: {COLORS['primary']} !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
        }}

        /* Primary button */
        button[kind="primary"] {{
            width: 100%;
            background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['primary_light']} 100%) !important;
            border: none !important;
            color: white !important;
            font-weight: 600;
            padding: 0.85rem 0;
            font-size: 1rem;
            border-radius: 12px !important;
        }}

        button[kind="primary"]:hover {{
            box-shadow: 0 4px 16px rgba(37, 99, 235, 0.4);
            transform: translateY(-1px);
        }}

        /* Secondary/link button */
        button[kind="secondary"] {{
            border: none !important;
            background: transparent !important;
            color: {COLORS['text_muted']} !important;
        }}

        button[kind="secondary"]:hover {{
            color: {COLORS['text_primary']} !important;
        }}

        /* Role badge */
        .role-badge {{
            display: inline-block;
            background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['primary_light']} 100%);
            color: white;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        /* Info box */
        .info-box {{
            background: rgba(37, 99, 235, 0.1);
            border: 1px solid rgba(37, 99, 235, 0.2);
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
        }}

        /* Hide Streamlit elements */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)


def _render_error_state(title: str, message: str, show_login_link: bool = False):
    """Render an error state with helpful message."""
    # Logo
    _render_logo()

    st.markdown(f'<h1 class="invite-title">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<div class="invite-subtitle">{message}</div>', unsafe_allow_html=True)

    if show_login_link:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Go to Login", type="primary", use_container_width=True):
                # Clear query params and redirect to login
                st.query_params.clear()
                st.session_state['auth_view'] = 'login'
                st.rerun()


def _render_logo():
    """Render the app logo."""
    try:
        from ui.theme import ThemeManager
        logo_data = ThemeManager.get_cached_logo('dark')

        if logo_data:
            st.markdown(
                f"""
                <div style="text-align: center; margin-bottom: 1rem;">
                    <img src="data:image/png;base64,{logo_data}" style="width: 280px; max-width: 80%; opacity: 1.0;">
                </div>
                """,
                unsafe_allow_html=True
            )
    except Exception:
        # Fallback if logo not available
        st.markdown(
            f"""
            <div style="text-align: center; margin-bottom: 1rem;">
                <h2 style="color: {COLORS['text_primary']}; font-weight: 700;">SADDL AdPulse</h2>
            </div>
            """,
            unsafe_allow_html=True
        )


def _render_account_setup_form(invitation: Invitation, token: str):
    """Render the account setup form for valid invitations."""
    # Logo
    _render_logo()

    # Header
    st.markdown('<h1 class="invite-title">Welcome! Set Up Your Account</h1>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="invite-subtitle">You\'ve been invited to join the team</div>',
        unsafe_allow_html=True
    )

    # Role info
    st.markdown(f"""
        <div class="info-box">
            <div style="text-align: center;">
                <span style="color: {COLORS['text_muted']}; font-size: 0.85rem;">You're joining as</span>
                <div style="margin-top: 8px;">
                    <span class="role-badge">{invitation.role}</span>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Account setup form
    with st.form("account_setup_form"):
        # Name fields
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input(
                "First Name",
                placeholder="John",
                help="Your first name"
            )
        with col2:
            last_name = st.text_input(
                "Last Name",
                placeholder="Smith",
                help="Your last name"
            )

        # Email (pre-filled, disabled)
        st.text_input(
            "Email",
            value=invitation.email,
            disabled=True,
            help="This is the email your invitation was sent to"
        )

        # Password fields
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Create a secure password",
            help="At least 8 characters with uppercase, lowercase, and a number"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Confirm your password"
        )

        # Password requirements hint
        st.caption(
            "Password must be at least 8 characters and include uppercase, "
            "lowercase, and a number."
        )

        # Terms checkbox
        agree_terms = st.checkbox(
            "I agree to the Terms of Service and Privacy Policy",
            value=False
        )

        # Submit button
        submitted = st.form_submit_button("Create Account", type="primary")

        if submitted:
            # Collect all validation errors
            errors = []

            if not first_name.strip():
                errors.append("First name is required")

            if not last_name.strip():
                errors.append("Last name is required")

            if not password:
                errors.append("Password is required")
            else:
                is_valid, pwd_errors = validate_password(password, confirm_password)
                if not is_valid:
                    errors.extend(pwd_errors)

            if not agree_terms:
                errors.append("You must agree to the Terms of Service")

            # Show all errors at once
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # All validation passed - create account
                success, user_id, error_msg = create_user_from_invitation(
                    invitation=invitation,
                    first_name=first_name.strip(),
                    last_name=last_name.strip(),
                    password=password
                )

                if success:
                    # Mark invitation as accepted
                    invitation_service = InvitationService()
                    invitation_service.accept_invitation(token, user_id)

                    # Auto-login the user
                    _auto_login_user(invitation.email, password)

                    # Set onboarding flag if enabled
                    if FEATURE_ONBOARDING_WIZARD:
                        st.session_state['show_onboarding'] = True

                    # Clear query params
                    st.query_params.clear()

                    # Show success and redirect
                    st.success("Account created successfully! Redirecting...")
                    st.balloons()

                    # Rerun to redirect to main app
                    st.session_state['_nav_loading'] = True
                    st.rerun()
                else:
                    st.error(f"Failed to create account: {error_msg}")

    # Back to login link
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Already have an account? Log in", type="secondary", use_container_width=True):
        st.query_params.clear()
        st.session_state['auth_view'] = 'login'
        st.rerun()


def _auto_login_user(email: str, password: str):
    """
    Automatically log in the newly created user.
    """
    try:
        auth = AuthService()
        result = auth.sign_in(email, password)

        if not result["success"]:
            # If auto-login fails, user will just need to log in manually
            st.warning("Account created! Please log in with your new credentials.")
    except Exception as e:
        st.warning(f"Account created! Please log in with your new credentials.")
