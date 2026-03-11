"""
Auth Service (V2)
=================
Handles user authentication against the V2 custom schema.
PRD Reference: ORG_USERS_ROLES_PRD.md §12

Replaces legacy Supabase Auth (auth/service.py).
"""

import os
import os
import re
import secrets
try:
    import streamlit as st
except ImportError:
    class MockSt:
        session_state = {}
    st = MockSt()

from typing import Optional, Dict, Any
from app_core.auth.models import User, Role, PasswordChangeResult
from app_core.auth.hashing import verify_password, hash_password
from app_core.postgres_manager import PostgresManager

# DB Driver Shim: Try psycopg2, fall back to psycopg (v3)
try:
    import psycopg2
    import psycopg2.errors
except ImportError:
    try:
        import psycopg as psycopg2 # Alias v3 to v2 name
        # V3 doesn't have 'errors' submodule in same way, map it
        import psycopg.errors
        psycopg2.errors = psycopg.errors
    except ImportError:
        raise ImportError("No Postgres driver found. Install psycopg2-binary or psycopg[binary].")

# Load env variables (robustness)
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


class AuthService:
    """
    V2 Authentication Service.
    Uses 'users' table in core Postgres schema.
    """
    
    def __init__(self):
        # Use shared PostgresManager for connection pooling
        from app_core.db_manager import get_db_manager
        self.db_manager = get_db_manager(test_mode=False) # Auth always uses live/postgres
        
        # Determine if we are actually using PostgresManager
        if not hasattr(self.db_manager, '_get_connection'):
             # Fallback if config is messed up and we got SQLite manager
             self.db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") 
             
    from contextlib import contextmanager
    @contextmanager
    def _get_connection(self):
        # Prefer using the pooled connection from PostgresManager
        if hasattr(self.db_manager, '_get_connection'):
            with self.db_manager._get_connection() as conn:
                yield conn
        else:
            # Fallback to direct connect
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

    def sign_in(self, email: str, password: str, org_id=None) -> Dict[str, Any]:
        """
        Authenticate user by email and password.
        Sets session state on success.
        Returns: {success: bool, user: User, error: str}
        """
        _expected_org_id = org_id  # capture before tuple-unpack shadows the name
        if not email or not password:
             return {"success": False, "error": "Email and password required"}
             
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                # Fetch user + password_hash
                ph = self.db_manager.placeholder
                query = f"""
                    SELECT id, organization_id, email, password_hash, role, billable, status, must_reset_password, password_updated_at
                    FROM users 
                    WHERE email = {ph} AND status = 'ACTIVE';
                """
                cur.execute(query, (email.lower().strip(),))
                row = cur.fetchone()
                
                # Close cursor inside context (connection stays open until exit)
                cur.close()
                
                if not row:
                    return {"success": False, "error": "User not found"}

                (uid, org_id, db_email, db_hash, role_str, billable, status, must_reset, pwd_updated) = row

                # Verify Password
                if not verify_password(password, db_hash):
                    return {"success": False, "error": "Invalid password"}

                # SEC-5: Org scoping — reject if caller supplied an org_id that doesn't match the DB row
                if _expected_org_id and str(org_id) != str(_expected_org_id):
                    return {'success': False, 'error': 'Account not found in this organization'}

                # Construct User Model
                # Load Overrides first
                account_overrides = {}
                try:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT amazon_account_id, role 
                        FROM user_account_overrides 
                        WHERE user_id = %s
                    """, (uid,))
                    for row_ov in cur.fetchall():
                        import uuid
                        # Parse UUID and Role
                        acc_id = uuid.UUID(str(row_ov[0])) # Ensure string if driver returns uuid
                        ov_role = Role(row_ov[1])
                        account_overrides[acc_id] = ov_role
                    cur.close()
                except Exception as e:
                    print(f"Warning: Failed to load overrides: {e}")
                    # Non-critical, continue login
                
                user = User(
                    id=uid,
                    organization_id=org_id,
                    email=db_email,
                    password_hash="REDACTED", # Don't keep hash in memory object
                    role=Role(role_str),
                    billable=billable,
                    status=status,
                    created_at=None,
                    must_reset_password=must_reset,
                    password_updated_at=pwd_updated,
                    account_overrides=account_overrides
                )
                
                # SESSION STORAGE (Canonical)
                import secrets as _secrets
                session_token = _secrets.token_urlsafe(32)
                st.session_state['session_token'] = session_token
                st.session_state["user"] = user

                return {"success": True, "user": user}
            
        except Exception as e:
            print(f"Auth Error: {e}")
            return {"success": False, "error": f"System error: {str(e)}"}

    def get_current_user(self) -> Optional[User]:
        """
        Get the currently authenticated user from session state.
        Type-safe accessor.
        """
        user = st.session_state.get("user")
        if user and isinstance(user, User):
            return user
        return None

    def validate_session(self) -> bool:
        """Return True only when both a user object and a session token are present."""
        return st.session_state.get('user') is not None and st.session_state.get('session_token') is not None

    def sign_out(self):
        """Clear user session."""
        if "user" in st.session_state:
            del st.session_state["user"]
        if "session_token" in st.session_state:
            del st.session_state["session_token"]

    def create_user_manual(self, email: str, password: str, role: Role, org_id: str) -> bool:
        """
        Helper for SEEDING only. Not for public registration.
        """
        try:
            hashed = hash_password(password)
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                ph = self.db_manager.placeholder
                cur.execute(f"""
                    INSERT INTO users (email, password_hash, role, organization_id, billable)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                """, (email.lower(), hashed, role.value, org_id, True))
                
                # context manager auto-commits if successful
                return True
        except Exception as e:
            print(f"Create Error: {e}")
            return False

    def list_users(self, organization_id: str) -> list[Dict[str, Any]]:
        """
        List all users in an organization.
        Returns list of dicts: {id, email, role, status, billable}
        """
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                ph = self.db_manager.placeholder
                cur.execute(f"""
                    SELECT id, email, role, status, billable 
                    FROM users 
                    WHERE organization_id = {ph}
                    ORDER BY created_at DESC
                """, (str(organization_id),))
                
                rows = cur.fetchall()
                cur.close()
                
                users = []
                for r in rows:
                    users.append({
                        "id": r[0],
                        "email": r[1],
                        "role": r[2],
                        "status": r[3],
                        "billable": r[4]
                    })
                return users
            
        except Exception as e:
            print(f"List Users Error: {e}")
            return []

    def create_user_invite(self, email: str, role: Role, org_id: str) -> Dict[str, Any]:
        """
        Create a new user (Invite flow).
        Since we don't have email sending yet, we set a temp password.
        Returns: {success: bool, error: str, temp_password: str}
        """
        temp_password = secrets.token_urlsafe(16)
        if not email or not role or not org_id:
            return {"success": False, "error": "Missing fields"}

        try:
            hashed = hash_password(temp_password)
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                # Check for existing
                ph = self.db_manager.placeholder
                cur.execute(f"SELECT id FROM users WHERE email = {ph}", (email.lower(),))
                if cur.fetchone():
                    return {"success": False, "error": "User already exists"}
                
                # Insert
                # Determine billable? (Simplified: Use default from role)
                from app_core.auth.permissions import get_billable_default
                billable = get_billable_default(role.value)
                
                cur.execute(f"""
                    INSERT INTO users (email, password_hash, role, organization_id, billable, status)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 'ACTIVE')
                """, (email.lower(), hashed, role.value, org_id, billable))
                
                # context manager auto-commits
                
                # Return instructions for the admin
                return {"success": True, "temp_password": temp_password}
            
        except Exception as e:
            print(f"Invite Error: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # PHASE 3.5: ACCOUNT ACCESS OVERRIDES
    # =========================================================================

    def update_user_role(self, user_id: str, new_role: Role, updated_by_user_id: str) -> Dict[str, Any]:
        """
        Update user's global role and auto-cleanup invalid overrides.
        """
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                # 1. Update Global Role
                cur.execute("""
                    UPDATE users 
                    SET role = %s 
                    WHERE id = %s
                """, (new_role.value, str(user_id)))
                
                # 2. Auto-cleanup: invalid overrides logic
                if new_role == Role.VIEWER:
                    cur.execute("""
                        DELETE FROM user_account_overrides
                        WHERE user_id = %s AND role = 'OPERATOR'
                    """, (str(user_id),))
                
                return {"success": True}
            
        except Exception as e:
            print(f"Update Role Error: {e}")
            return {"success": False, "error": str(e)}

    def set_account_override(self, user_id: str, account_id: str, override_role: Role, set_by_user_id: str) -> Dict[str, Any]:
        """
        Set or update an account access override.
        """
        # Validate allowed override roles (Phase 3.5: VIEWER/OPERATOR only)
        if override_role not in [Role.VIEWER, Role.OPERATOR]:
            return {"success": False, "error": "Overrides can only be VIEWER or OPERATOR"}

        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                # 1. Fetch user's global role validation (Application level double-check)
                cur.execute("SELECT role FROM users WHERE id = %s", (str(user_id),))
                row = cur.fetchone()
                if not row:
                    return {"success": False, "error": "User not found"}
                    
                global_role_str = row[0]
                from app_core.auth.permissions import ROLE_HIERARCHY_STR
                
                global_level = ROLE_HIERARCHY_STR.get(global_role_str, 0)
                override_level = ROLE_HIERARCHY_STR.get(override_role.value, 0)
                
                # Verify downgrade-only rule
                if override_level > global_level:
                    return {"success": False, "error": "Cannot set override higher than global role"}
                
                # 2. Upsert Override
                cur.execute("""
                    INSERT INTO user_account_overrides (user_id, amazon_account_id, role, created_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, amazon_account_id)
                    DO UPDATE SET role = EXCLUDED.role;
                """, (str(user_id), str(account_id), override_role.value, str(set_by_user_id)))
                
                return {"success": True}
            
        except Exception as e:
            print(f"Set Override Error: {e}")
            if "check_override_downgrade" in str(e):
                 return {"success": False, "error": "Database rejected: Override cannot exceed global role"}
            return {"success": False, "error": str(e)}

    def remove_account_override(self, user_id: str, account_id: str) -> Dict[str, Any]:
        """Remove an access override, reverting to global role."""
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    DELETE FROM user_account_overrides 
                    WHERE user_id = %s AND amazon_account_id = %s
                """, (str(user_id), str(account_id)))
                
                return {"success": True}
        except Exception as e:
            print(f"Remove Override Error: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # PHASE 3: SECURITY & PASSWORD MANAGEMENT
    # =========================================================================

    def validate_password_strength(self, password: str) -> bool:
        """
        Policy: Min 8 chars, at least 1 number or special char.
        """
        if len(password) < 8:
            return False
        if not re.search(r'[0-9!@#$%^&*(),.?":{}|<>]', password):
            return False
        return True

    def change_password(self, user_id: str, old_password: str, new_password: str) -> PasswordChangeResult:
        """
        Self-service password change.
        """
        if not self.validate_password_strength(new_password):
            return PasswordChangeResult(False, "Password too weak. Must be 8+ chars with a number or symbol.")
            
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                # 1. Verify Old Password
                cur.execute("SELECT password_hash FROM users WHERE id = %s", (str(user_id),))
                row = cur.fetchone()
                if not row:
                    return PasswordChangeResult(False, "User not found.")
                    
                db_hash = row[0]
                if not verify_password(old_password, db_hash):
                    return PasswordChangeResult(False, "Current password incorrect.")
                    
                # 2. Update to New Password
                new_hash = hash_password(new_password)
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s, 
                        password_updated_at = NOW(), 
                        must_reset_password = FALSE 
                    WHERE id = %s
                """, (new_hash, str(user_id)))
                
                return PasswordChangeResult(True, "Password updated successfully.")
            
        except Exception as e:
            print(f"Change Password Error: {e}")
            return PasswordChangeResult(False, "System error.")

    def admin_reset_password(self, admin_user: User, target_user_id: str) -> PasswordChangeResult:
        """
        Admin-assisted recovery.
        """
        import secrets as _secrets
        temp_password = _secrets.token_urlsafe(12) + 'Aa1!'

        try:
            with self._get_connection() as conn:
                cur = conn.cursor()

                # 1. Fetch Target Role (for protection)
                cur.execute("SELECT role FROM users WHERE id = %s", (str(target_user_id),))
                row = cur.fetchone()
                if not row:
                    return PasswordChangeResult(False, "Target user not found.")
                    
                target_role = row[0]
                
                # RULE: STRICT HIERARCHY CHECK
                from app_core.auth.permissions import can_manage_role
                manager_role_str = admin_user.role.value if hasattr(admin_user.role, 'value') else str(admin_user.role)
                
                if not can_manage_role(manager_role_str, target_role):
                    return PasswordChangeResult(False, f"Insufficient privileges. {manager_role_str} cannot manage {target_role}.")
                
                # 2. Update
                new_hash = hash_password(temp_password)
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s, 
                        must_reset_password = TRUE 
                    WHERE id = %s
                """, (new_hash, str(target_user_id)))
                
                return PasswordChangeResult(True, temp_password)
            
        except Exception as e:
            print(f"Admin Reset Error: {e}")
            return PasswordChangeResult(False, str(e))

    def request_password_reset(self, email: str) -> bool:
        """
        Public endpoint for 'Forgot Password'.
        """
        if not email:
            return False
            
        try:
            # Check existence first (quick read)
            exists = False
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE email = %s", (email.lower().strip(),))
                exists = cur.fetchone() is not None
            
            if exists:
                import secrets as _secrets
                temp_password = _secrets.token_urlsafe(12) + 'Aa1!'
                new_hash = hash_password(temp_password)
                
                # Update DB
                with self._get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE users 
                        SET password_hash = %s, 
                            must_reset_password = TRUE,
                            password_updated_at = NOW()
                        WHERE email = %s
                    """, (new_hash, email.lower().strip()))
                
                # Send Email
                from utils.email_sender import EmailSender
                sender = EmailSender()
                
                subject = "Password Reset - Saddle"
                html = f"""
                <div style="font-family: sans-serif; color: #333;">
                    <h2>Password Reset</h2>
                    <p>Your temporary password is:</p>
                    <p style="font-size: 18px; font-weight: bold; background: #f4f4f5; padding: 10px; border-radius: 6px; display: inline-block;">
                        {temp_password}
                    </p>
                    <p>Please log in with this password. You will be asked to create a new one immediately.</p>
                    <br>
                    <small>If you did not request this, please contact support.</small>
                </div>
                """
                
                success = sender.send_email(email, subject, html)
                if success:
                    print(f"Password reset email sent to {email}")
                else:
                    print(f"Failed to send email to {email}")
                
            return True
            
        except Exception as e:
            print(f"Reset Request Error: {e}")
            return False
