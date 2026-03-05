-- ============================================================================
-- Migration 005: User Invitations Table
-- ============================================================================
-- Phase 1 of Automated User Onboarding Implementation
--
-- Purpose:
--   Creates the user_invitations table to store secure invitation tokens
--   that replace the legacy temp password display system.
--
-- Usage:
--   Run this migration against your PostgreSQL database:
--   psql -d your_database -f 005_user_invitations.sql
--
-- Rollback:
--   DROP TABLE IF EXISTS user_invitations CASCADE;
--
-- Author: SADDL Engineering
-- Date: 2025-01
-- ============================================================================

-- Wrap in transaction for safe rollback on failure
BEGIN;

-- ============================================================================
-- Create user_invitations table
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_invitations (
    -- Primary key: UUID auto-generated
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Email address of the invited user
    -- Not unique because same email can have multiple invitations (different orgs)
    email VARCHAR(255) NOT NULL,

    -- Secure random token for invitation link
    -- Must be unique to prevent collisions
    token VARCHAR(255) UNIQUE NOT NULL,

    -- Organization the user is being invited to
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- User who sent the invitation (for audit trail)
    invited_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,

    -- Role the invited user will have
    -- Matches the role enum used in users table
    role VARCHAR(20) NOT NULL CHECK (role IN ('OWNER', 'ADMIN', 'OPERATOR', 'VIEWER')),

    -- Invitation status
    -- pending: waiting for user to accept
    -- accepted: user has created account
    -- expired: token has passed expiration date
    -- revoked: admin manually cancelled invitation
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),

    -- When the invitation token expires
    -- Default: 7 days from creation
    expires_at TIMESTAMPTZ NOT NULL,

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,

    -- Optional: ID of user created from this invitation (for linking)
    created_user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================================
-- Create indexes for performance
-- ============================================================================

-- Fast token lookups (primary use case: validating invitation links)
CREATE INDEX IF NOT EXISTS idx_user_invitations_token
    ON user_invitations(token);

-- Find invitations by email (check for duplicates, resend flow)
CREATE INDEX IF NOT EXISTS idx_user_invitations_email
    ON user_invitations(email);

-- Filter by organization (admin views)
CREATE INDEX IF NOT EXISTS idx_user_invitations_organization
    ON user_invitations(organization_id);

-- Filter by status (find pending invitations)
CREATE INDEX IF NOT EXISTS idx_user_invitations_status
    ON user_invitations(status);

-- Composite index for common query: pending invitations for an org
CREATE INDEX IF NOT EXISTS idx_user_invitations_org_status
    ON user_invitations(organization_id, status);

-- Find expired invitations for cleanup
CREATE INDEX IF NOT EXISTS idx_user_invitations_expires_at
    ON user_invitations(expires_at)
    WHERE status = 'pending';

-- ============================================================================
-- Add comments for documentation
-- ============================================================================

COMMENT ON TABLE user_invitations IS
    'Stores secure invitation tokens for new user onboarding. Replaces legacy temp password system.';

COMMENT ON COLUMN user_invitations.token IS
    'Cryptographically secure random token (32 bytes, URL-safe base64). Used in invitation link.';

COMMENT ON COLUMN user_invitations.status IS
    'Current state: pending (awaiting acceptance), accepted (user created), expired (past expiry), revoked (manually cancelled)';

COMMENT ON COLUMN user_invitations.expires_at IS
    'Token expiration timestamp. Default 7 days. Expired tokens cannot be used.';

COMMENT ON COLUMN user_invitations.created_user_id IS
    'Links to the user account created from this invitation. Set when invitation is accepted.';

-- ============================================================================
-- Optional: Function to auto-expire invitations
-- ============================================================================
-- This function can be called periodically to mark expired invitations

CREATE OR REPLACE FUNCTION expire_old_invitations()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE user_invitations
    SET status = 'expired'
    WHERE status = 'pending'
      AND expires_at < NOW();

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_invitations() IS
    'Marks pending invitations as expired if past their expiration date. Returns count of updated rows.';

-- ============================================================================
-- Optional: View for admin dashboard
-- ============================================================================

CREATE OR REPLACE VIEW v_invitation_summary AS
SELECT
    ui.id,
    ui.email,
    ui.role,
    ui.status,
    ui.created_at,
    ui.expires_at,
    ui.accepted_at,
    o.name AS organization_name,
    inviter.email AS invited_by_email,
    CASE
        WHEN ui.status = 'pending' AND ui.expires_at < NOW() THEN 'expired'
        ELSE ui.status
    END AS effective_status,
    CASE
        WHEN ui.status = 'pending' AND ui.expires_at > NOW()
        THEN EXTRACT(EPOCH FROM (ui.expires_at - NOW())) / 3600
        ELSE NULL
    END AS hours_until_expiry
FROM user_invitations ui
JOIN organizations o ON ui.organization_id = o.id
LEFT JOIN users inviter ON ui.invited_by_user_id = inviter.id;

COMMENT ON VIEW v_invitation_summary IS
    'Admin-friendly view of invitations with organization and inviter details.';

-- ============================================================================
-- Commit transaction
-- ============================================================================
COMMIT;

-- ============================================================================
-- Verification queries (run manually to verify migration)
-- ============================================================================
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'user_invitations'
-- ORDER BY ordinal_position;
--
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'user_invitations';
