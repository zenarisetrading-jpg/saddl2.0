"""
Invitation Service Module for SADDL AdPulse
============================================

Standalone service for managing user invitations with secure email links.
Replaces the legacy temp password display system.

This module is designed to be:
1. Standalone - Can be tested independently without main app
2. Database-agnostic - Uses same PostgresManager patterns
3. Feature-flagged - Can be enabled/disabled via environment variable

Usage:
    from app_core.auth.invitation_service import InvitationService

    service = InvitationService()

    # Create and send invitation
    result = service.create_invitation(
        email="newuser@example.com",
        organization_id="uuid-here",
        invited_by_user_id="admin-uuid",
        role="OPERATOR",
        inviter_name="John Admin",
        org_name="Acme Corp"
    )

    # Validate token from invitation link
    invitation = service.validate_token("token-from-url")

    # Accept invitation (after user sets password)
    service.accept_invitation(token="...", created_user_id="new-user-uuid")

PRD Reference: Automated User Onboarding Implementation Plan - Phase 1
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum
from app_core.auth.hashing import hash_password, verify_password

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from multiple locations (matching main app pattern)
from pathlib import Path
try:
    from dotenv import load_dotenv
    current_dir = Path(__file__).parent.parent.parent  # Go up from app_core/auth/ to desktop/
    load_dotenv(current_dir / '.env')           # desktop/.env
    load_dotenv(current_dir.parent / '.env')    # saddle/.env (parent directory)
except ImportError:
    pass


# ============================================================================
# DATA CLASSES
# ============================================================================

class InvitationStatus(Enum):
    """Possible states of an invitation."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class Invitation:
    """
    Represents a user invitation record.
    """
    id: str
    email: str
    token: str
    organization_id: str
    invited_by_user_id: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None
    created_user_id: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if invitation can still be accepted."""
        return self.status == InvitationStatus.PENDING.value and not self.is_expired


class InvitationResult(NamedTuple):
    """Result of an invitation operation."""
    success: bool
    message: str
    invitation: Optional[Invitation] = None
    error_code: Optional[str] = None


# ============================================================================
# INVITATION SERVICE
# ============================================================================

class InvitationService:
    """
    Manages user invitations with secure token-based email links.

    Responsibilities:
    - Generate secure invitation tokens
    - Store invitations in database
    - Send invitation emails
    - Validate tokens from invitation links
    - Mark invitations as accepted

    All database operations use parameterized queries to prevent SQL injection.
    All operations are wrapped in try-except for graceful error handling.
    """

    # Token configuration
    TOKEN_BYTES = 32  # 256 bits of randomness
    DEFAULT_EXPIRY_DAYS = 7

    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize the invitation service.

        Args:
            db_url: PostgreSQL connection string. If provided, overrides default manager.
        """
        if db_url:
            self.db_url = db_url
            self.db_manager = None
        else:
            from app_core.db_manager import get_db_manager
            self.db_manager = get_db_manager(test_mode=False)
            self.db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")

        if not self.db_url and (not self.db_manager or not hasattr(self.db_manager, '_get_connection')):
            logger.warning("No DATABASE_URL configured. Database operations will fail.")

        # Import email sender lazily to avoid circular imports
        self._email_sender = None

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Get config from env vars or streamlit secrets."""
        # 1. Try environment variable
        val = os.environ.get(key)
        if val is not None:
            return val
        
        # 2. Try Streamlit secrets
        try:
            import streamlit as st
            # Check root level
            if key in st.secrets:
                return str(st.secrets[key])
            # Check [env] section
            if "env" in st.secrets and key in st.secrets["env"]:
                return str(st.secrets["env"][key])
        except Exception:
            pass
            
        return default

    from contextlib import contextmanager
    @contextmanager
    def _get_connection(self):
        """
        Get a database connection.
        Uses shared pool if available, otherwise direct connect.
        """
        if self.db_manager and hasattr(self.db_manager, '_get_connection'):
            with self.db_manager._get_connection() as conn:
                yield conn
        else:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                try:
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.close()
            except ImportError:
                try:
                    import psycopg
                    conn = psycopg.connect(self.db_url)
                    try:
                        yield conn
                        conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                    finally:
                        conn.close()
                except ImportError:
                    raise ImportError("No PostgreSQL driver found. Install psycopg2-binary or psycopg.")

    def _get_email_sender(self):
        """Lazy-load email sender to avoid import issues."""
        if self._email_sender is None:
            from utils.email_sender import EmailSender
            self._email_sender = EmailSender()
        return self._email_sender

    @staticmethod
    def _generate_token() -> str:
        """
        Generate a cryptographically secure random token.
        """
        return secrets.token_urlsafe(InvitationService.TOKEN_BYTES)

    def _get_expiry_date(self) -> datetime:
        """
        Calculate the expiration date for a new invitation.
        """
        days = int(self._get_config("INVITATION_EXPIRY_DAYS", self.DEFAULT_EXPIRY_DAYS))
        return datetime.now(timezone.utc) + timedelta(days=days)

    def _get_app_url(self) -> str:
        """Get the base application URL for invitation links."""
        url = self._get_config("APP_URL", "http://localhost:8501")
        # Ensure URL always has a scheme (https preferred for production)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        return url

    # =========================================================================
    # CORE OPERATIONS
    # =========================================================================

    def create_invitation(
        self,
        email: str,
        organization_id: str,
        invited_by_user_id: str,
        role: str,
        inviter_name: str = "Your administrator",
        inviter_org_name: str = "your organization"
    ) -> InvitationResult:
        """
        Create a new invitation and send email.
        """
        # Validate inputs
        email = email.lower().strip()
        if not email or "@" not in email:
            return InvitationResult(
                success=False,
                message="Invalid email address",
                error_code="INVALID_EMAIL"
            )

        if role not in ["VIEWER", "OPERATOR", "ADMIN", "OWNER"]:
            return InvitationResult(
                success=False,
                message=f"Invalid role: {role}",
                error_code="INVALID_ROLE"
            )

        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                # Check for existing pending invitation for this email + org
                cur.execute("""
                    SELECT id, token, expires_at, created_at
                    FROM user_invitations
                    WHERE email = %s
                      AND organization_id = %s
                      AND status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (email, organization_id))

                existing = cur.fetchone()

                if existing:
                    # Resend existing invitation
                    inv_id, token, expires_at, created_at = existing

                    # Check if expired - if so, create new one instead
                    if expires_at < datetime.now(timezone.utc):
                        # Mark old one as expired
                        cur.execute("""
                            UPDATE user_invitations
                            SET status = 'expired'
                            WHERE id = %s
                        """, (inv_id,))
                        logger.info(f"Marked expired invitation {inv_id} for {email}")
                    else:
                        # Resend existing valid invitation
                        logger.info(f"Resending existing invitation {inv_id} for {email}")
                        cur.close()

                        # Send email (don't fail if email fails)
                        email_sent = self._send_invitation_email(
                            email=email,
                            token=token,
                            inviter_name=inviter_name,
                            org_name=inviter_org_name,
                            role=role
                        )
                        
                        # Note: We closed cursor/conn early for perf, but context manager commits on exit 
                        # so updates above are safe.
                        
                        invitation = Invitation(
                            id=str(inv_id),
                            email=email,
                            token=token,
                            organization_id=organization_id,
                            invited_by_user_id=invited_by_user_id,
                            role=role,
                            status="pending",
                            expires_at=expires_at,
                            created_at=created_at
                        )

                        return InvitationResult(
                            success=True,
                            message="Invitation resent" if email_sent else "Invitation found but email failed to send",
                            invitation=invitation
                        )

                # Create new invitation
                token = self._generate_token()
                token_hash = hash_password(token)
                expires_at = self._get_expiry_date()

                cur.execute("""
                    INSERT INTO user_invitations (
                        email, token, organization_id, invited_by_user_id,
                        role, status, expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 'pending', %s)
                    RETURNING id, created_at
                """, (email, token_hash, organization_id, invited_by_user_id, role, expires_at))

                result = cur.fetchone()
                inv_id, created_at = result
                
                # Context manager will commit on exit

                logger.info(f"Created invitation {inv_id} for {email} as {role}")

                # Send invitation email
                email_sent = self._send_invitation_email(
                    email=email,
                    token=token,
                    inviter_name=inviter_name,
                    org_name=inviter_org_name,
                    role=role
                )

                cur.close()

                invitation = Invitation(
                    id=str(inv_id),
                    email=email,
                    token=token,
                    organization_id=organization_id,
                    invited_by_user_id=invited_by_user_id,
                    role=role,
                    status="pending",
                    expires_at=expires_at,
                    created_at=created_at
                )

                if email_sent:
                    return InvitationResult(
                        success=True,
                        message=f"Invitation sent to {email}",
                        invitation=invitation
                    )
                else:
                    return InvitationResult(
                        success=True,
                        message=f"Invitation created but email failed to send. Token: {token[:8]}...",
                        invitation=invitation,
                        error_code="EMAIL_FAILED"
                    )

        except Exception as e:
            logger.error(f"Create invitation error: {e}")
            return InvitationResult(
                success=False,
                message=f"Failed to create invitation: {str(e)}",
                error_code="DATABASE_ERROR"
            )

    def validate_token(self, token: str) -> Optional[Invitation]:
        """
        Validate an invitation token from a URL.
        """
        if not token:
            return None

        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                # Fetch all pending, non-expired invitations and bcrypt-verify in Python
                # (bcrypt hashes cannot be matched in SQL; invitation volume is low)
                cur.execute("""
                    SELECT id, email, token, organization_id, invited_by_user_id,
                           role, status, expires_at, created_at, accepted_at, created_user_id
                    FROM user_invitations
                    WHERE status = 'pending'
                """)

                rows = cur.fetchall()
                row = None
                for candidate in rows:
                    stored_hash = candidate[2]
                    if verify_password(token, stored_hash):
                        row = candidate
                        break

                if not row:
                    logger.warning(f"Token not found: {token[:8]}...")
                    return None

                invitation = Invitation(
                    id=str(row[0]),
                    email=row[1],
                    token=row[2],
                    organization_id=str(row[3]),
                    invited_by_user_id=str(row[4]),
                    role=row[5],
                    status=row[6],
                    expires_at=row[7] if row[7].tzinfo else row[7].replace(tzinfo=timezone.utc),
                    created_at=row[8],
                    accepted_at=row[9],
                    created_user_id=str(row[10]) if row[10] else None
                )

                # Check expiration
                if invitation.is_expired:
                    # Mark as expired in database
                    cur.execute("""
                        UPDATE user_invitations
                        SET status = 'expired'
                        WHERE id = %s
                    """, (invitation.id,))
                    # Auto-commit on exit
                    logger.info(f"Token expired: {token[:8]}...")
                    return None

                logger.info(f"Token valid for {invitation.email}")
                return invitation

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    def accept_invitation(self, token: str, created_user_id: str) -> InvitationResult:
        """
        Mark an invitation as accepted after user account creation.
        """
        if not token or not created_user_id:
            return InvitationResult(
                success=False,
                message="Token and user ID required",
                error_code="MISSING_PARAMS"
            )

        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                # Fetch pending invitations and bcrypt-verify token in Python
                cur.execute("""
                    SELECT id, email, token
                    FROM user_invitations
                    WHERE status = 'pending'
                """)
                rows = cur.fetchall()
                matched = None
                for candidate in rows:
                    stored_hash = candidate[2]
                    if verify_password(token, stored_hash):
                        matched = candidate
                        break

                if not matched:
                    return InvitationResult(
                        success=False,
                        message="Invitation not found or already accepted",
                        error_code="NOT_FOUND"
                    )

                inv_id, email, _ = matched

                cur.execute("""
                    UPDATE user_invitations
                    SET status = 'accepted',
                        accepted_at = NOW(),
                        created_user_id = %s
                    WHERE id = %s
                      AND status = 'pending'
                    RETURNING id, email
                """, (created_user_id, inv_id))

                result = cur.fetchone()

                if not result:
                    return InvitationResult(
                        success=False,
                        message="Invitation not found or already accepted",
                        error_code="NOT_FOUND"
                    )

                inv_id, email = result
                # Auto-commit on exit

                logger.info(f"Invitation {inv_id} accepted by user {created_user_id}")

                return InvitationResult(
                    success=True,
                    message=f"Invitation accepted for {email}"
                )

        except Exception as e:
            logger.error(f"Accept invitation error: {e}")
            return InvitationResult(
                success=False,
                message=f"Failed to accept invitation: {str(e)}",
                error_code="DATABASE_ERROR"
            )

    def revoke_invitation(self, invitation_id: str, revoked_by_user_id: str) -> InvitationResult:
        """
        Revoke a pending invitation (admin action).
        """
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                cur.execute("""
                    UPDATE user_invitations
                    SET status = 'revoked'
                    WHERE id = %s
                      AND status = 'pending'
                    RETURNING email
                """, (invitation_id,))

                result = cur.fetchone()

                if not result:
                    return InvitationResult(
                        success=False,
                        message="Invitation not found or not pending",
                        error_code="NOT_FOUND"
                    )

                email = result[0]
                # Auto-commit on exit

                logger.info(f"Invitation for {email} revoked by {revoked_by_user_id}")

                return InvitationResult(
                    success=True,
                    message=f"Invitation for {email} has been revoked"
                )

        except Exception as e:
            logger.error(f"Revoke invitation error: {e}")
            return InvitationResult(
                success=False,
                message=f"Failed to revoke invitation: {str(e)}",
                error_code="DATABASE_ERROR"
            )

    def list_invitations(
        self,
        organization_id: str,
        status_filter: Optional[str] = None
    ) -> list[Invitation]:
        """
        List invitations for an organization.
        """
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                if status_filter:
                    cur.execute("""
                        SELECT id, email, token, organization_id, invited_by_user_id,
                               role, status, expires_at, created_at, accepted_at, created_user_id
                        FROM user_invitations
                        WHERE organization_id = %s AND status = %s
                        ORDER BY created_at DESC
                    """, (organization_id, status_filter))
                else:
                    cur.execute("""
                        SELECT id, email, token, organization_id, invited_by_user_id,
                               role, status, expires_at, created_at, accepted_at, created_user_id
                        FROM user_invitations
                        WHERE organization_id = %s
                        ORDER BY created_at DESC
                    """, (organization_id,))

                rows = cur.fetchall()
                cur.close()

                invitations = []
                for row in rows:
                    invitations.append(Invitation(
                        id=str(row[0]),
                        email=row[1],
                        token=row[2],
                        organization_id=str(row[3]),
                        invited_by_user_id=str(row[4]),
                        role=row[5],
                        status=row[6],
                        expires_at=row[7] if row[7].tzinfo else row[7].replace(tzinfo=timezone.utc),
                        created_at=row[8],
                        accepted_at=row[9],
                        created_user_id=str(row[10]) if row[10] else None
                    ))

                return invitations

        except Exception as e:
            logger.error(f"List invitations error: {e}")
            return []


    def resend_invitation(
        self,
        invitation_id: str,
        inviter_name: str = "Your administrator",
        inviter_org_name: str = "your organization"
    ) -> InvitationResult:
        """
        Resend an invitation email for a pending invitation.
        """
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                cur.execute("""
                    SELECT email, token, role, status, expires_at
                    FROM user_invitations
                    WHERE id = %s
                """, (invitation_id,))

                row = cur.fetchone()
                
                # We can close connection now for check phase, but better to keep open for atomicity if we were doing more
                # Here we just read.

                if not row:
                    return InvitationResult(
                        success=False,
                        message="Invitation not found",
                        error_code="NOT_FOUND"
                    )

                email, token, role, status, expires_at = row

                if status != "pending":
                    return InvitationResult(
                        success=False,
                        message=f"Cannot resend - invitation is {status}",
                        error_code="INVALID_STATUS"
                    )

                # Make expires_at timezone-aware if it isn't
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if expires_at < datetime.now(timezone.utc):
                    return InvitationResult(
                        success=False,
                        message="Cannot resend - invitation has expired",
                        error_code="EXPIRED"
                    )

                # Log before action
                logger.info(f"Resending invitation to {email}")
                
                # Close DB resource before slow email send
                cur.close()

                email_sent = self._send_invitation_email(
                    email=email,
                    token=token,
                    inviter_name=inviter_name,
                    org_name=inviter_org_name,
                    role=role
                )

                if email_sent:
                    # DEBUG: Include sender info in message for troubleshooting
                    sender = self._get_email_sender()
                    debug = sender.get_debug_info()
                    return InvitationResult(
                        success=True,
                        message=f"Invitation resent to {email} (From: {debug['from_email']})"
                    )
                else:
                    return InvitationResult(
                        success=False,
                        message="Failed to send email",
                        error_code="EMAIL_FAILED"
                    )

        except Exception as e:
            logger.error(f"Resend invitation error: {e}")
            return InvitationResult(
                success=False,
                message=f"Failed to resend: {str(e)}",
                error_code="DATABASE_ERROR"
            )

    # =========================================================================
    # EMAIL SENDING
    # =========================================================================

    def _send_invitation_email(
        self,
        email: str,
        token: str,
        inviter_name: str,
        org_name: str,
        role: str
    ) -> bool:
        """
        Send the invitation email.

        Args:
            email: Recipient email address
            token: Invitation token
            inviter_name: Name of the person who sent the invite
            org_name: Organization name
            role: Role being assigned

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            sender = self._get_email_sender()

            # Construct invitation URL
            app_url = self._get_app_url().rstrip('/')
            # Use query parameter on root URL for Streamlit handling
            invitation_url = f"{app_url}/?token={token}"

            # Get email template
            html_content = self._get_invitation_email_html(
                inviter_name=inviter_name,
                org_name=org_name,
                role=role,
                invitation_url=invitation_url,
                expiry_days=int(self._get_config("INVITATION_EXPIRY_DAYS", self.DEFAULT_EXPIRY_DAYS))
            )

            subject = f"You've been invited to join {org_name} on SADDL AdPulse"

            success = sender.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content
            )

            if success:
                logger.info(f"Invitation email sent to {email}")
            else:
                logger.warning(f"Failed to send invitation email to {email}")

            return success

        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return False

    def _get_invitation_email_html(
        self,
        inviter_name: str,
        org_name: str,
        role: str,
        invitation_url: str,
        expiry_days: int
    ) -> str:
        """
        Generate the invitation email HTML content.

        Returns a professional, branded HTML email template.
        """
        # Import template if available, otherwise use inline
        try:
            from app_core.auth.email_templates import get_invitation_email_template
            return get_invitation_email_template(
                inviter_name=inviter_name,
                org_name=org_name,
                role=role,
                invitation_url=invitation_url,
                expiry_days=expiry_days
            )
        except ImportError:
            # Fallback inline template
            return self._get_fallback_email_template(
                inviter_name, org_name, role, invitation_url, expiry_days
            )

    def _get_fallback_email_template(
        self,
        inviter_name: str,
        org_name: str,
        role: str,
        invitation_url: str,
        expiry_days: int
    ) -> str:
        """Fallback email template if template file not available."""
        role_descriptions = {
            "VIEWER": "view campaign performance and reports",
            "OPERATOR": "manage campaigns and view reports",
            "ADMIN": "manage team members, campaigns, and settings",
            "OWNER": "full administrative access to your organization"
        }
        role_desc = role_descriptions.get(role, "access the platform")
        
        # Logo URL - use the publicly hosted logo from landing page
        # saddl.io is the live landing page, logo.png exists there
        logo_url = self._get_config("LOGO_URL_PUBLIC", "https://saddl.io/logo.png")

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%); border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px 40px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <!-- Icon/Logo Left -->
                                    <td width="60" style="vertical-align: middle;">
                                        <img src="{logo_url}" alt="Logo" width="48" height="48" style="display: block; border-radius: 8px;">
                                    </td>
                                    <!-- Text Right -->
                                    <td style="vertical-align: middle; padding-left: 16px;">
                                        <h1 style="color: #f1f5f9; font-size: 24px; margin: 0 0 4px 0; font-weight: 700;">
                                            SADDL AdPulse
                                        </h1>
                                        <p style="color: #64748b; font-size: 14px; margin: 0;">
                                            Decision-First PPC Platform
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px 40px 40px;">
                            <h2 style="color: #f1f5f9; font-size: 24px; margin: 0 0 16px 0; font-weight: 600;">
                                You're Invited!
                            </h2>

                            <p style="color: #cbd5e1; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                <strong style="color: #f1f5f9;">{inviter_name}</strong> has invited you to join
                                <strong style="color: #f1f5f9;">{org_name}</strong> on SADDL AdPulse.
                            </p>

                            <div style="background: rgba(37, 99, 235, 0.1); border: 1px solid rgba(37, 99, 235, 0.3); border-radius: 12px; padding: 16px 20px; margin-bottom: 24px;">
                                <p style="color: #60a5fa; font-size: 14px; margin: 0;">
                                    <strong>Your Role:</strong> {role}
                                </p>
                                <p style="color: #94a3b8; font-size: 13px; margin: 8px 0 0 0;">
                                    As a {role}, you'll be able to {role_desc}.
                                </p>
                            </div>

                            <!-- Bulletproof Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 8px 0 24px 0;">
                                        <table cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td bgcolor="#2563eb" style="border-radius: 12px; box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);">
                                                    <a href="{invitation_url}" target="_blank"
                                                       style="display: inline-block; padding: 16px 48px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; font-family: sans-serif; border: 1px solid #2563eb; border-radius: 12px;">
                                                        Accept Invitation
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0; text-align: center;">
                                This invitation expires in <strong>{expiry_days} days</strong>.
                                <br>
                                If you didn't expect this invitation, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; border-top: 1px solid rgba(255,255,255,0.1); text-align: center;">
                            <p style="color: #475569; font-size: 12px; margin: 0;">
                                SADDL AdPulse - The Decision-First PPC Platform
                                <br>
                                Questions? Contact your administrator.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


# ============================================================================
# STANDALONE TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Run this file directly to test the InvitationService in isolation.

    Usage:
        python -m core.auth.invitation_service

    Requires:
        - DATABASE_URL environment variable set
        - SMTP credentials configured (for email tests)
    """
    print("=" * 60)
    print("SADDL AdPulse - Invitation Service Standalone Test")
    print("=" * 60)

    # Check environment
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("\n[ERROR] No DATABASE_URL configured!")
        print("Set DATABASE_URL or SUPABASE_DB_URL environment variable.")
        exit(1)

    print(f"\nDatabase URL: {db_url[:30]}...")
    print(f"App URL: {os.environ.get('APP_URL', 'http://localhost:8501')}")
    print(f"SMTP configured: {bool(os.environ.get('SMTP_HOST'))}")

    # Initialize service
    service = InvitationService()

    print("\n[TEST] Token generation:")
    token = service._generate_token()
    print(f"  Generated token: {token[:20]}... ({len(token)} chars)")

    print("\n[TEST] Expiry calculation:")
    expiry = service._get_expiry_date()
    print(f"  Expires at: {expiry}")

    print("\n[OK] Invitation Service initialized successfully!")
    print("\nTo test full flow, call create_invitation() with valid UUIDs.")
