"""
Email Templates for SADDL AdPulse
==================================

Professional HTML email templates for user invitations and notifications.
Uses glassmorphic design language consistent with the main application.

Templates are designed to:
- Work across all major email clients (Gmail, Outlook, Apple Mail)
- Degrade gracefully when CSS is limited
- Be mobile-responsive
- Match SADDL AdPulse brand identity

Usage:
    from app_core.auth.email_templates import get_invitation_email_template

    html = get_invitation_email_template(
        inviter_name="John Admin",
        org_name="Acme Corp",
        role="OPERATOR",
        invitation_url="https://app.saddl.io/accept-invite?token=...",
        expiry_days=7
    )
"""

from typing import Optional


# ============================================================================
# BRAND COLORS (Email-safe versions)
# ============================================================================
# Note: Email clients have limited CSS support, so we use inline styles
# and email-safe color values

BRAND_COLORS = {
    'background': '#0f172a',
    'background_light': '#1e293b',
    'primary': '#2563eb',
    'primary_light': '#3b82f6',
    'text_primary': '#f1f5f9',
    'text_secondary': '#cbd5e1',
    'text_muted': '#64748b',
    'border': 'rgba(255,255,255,0.1)',
    'success': '#10b981',
    'warning': '#f59e0b',
}


# ============================================================================
# INVITATION EMAIL TEMPLATE
# ============================================================================

def get_invitation_email_template(
    inviter_name: str,
    org_name: str,
    role: str,
    invitation_url: str,
    expiry_days: int = 7
) -> str:
    """
    Generate the invitation email HTML.

    Args:
        inviter_name: Name of the person sending the invite
        org_name: Name of the organization
        role: Role being assigned (VIEWER, OPERATOR, ADMIN, OWNER)
        invitation_url: Full URL for the invitation acceptance page
        expiry_days: Number of days until the invitation expires

    Returns:
        Complete HTML email string
    """
    # Role descriptions for context
    role_descriptions = {
        "VIEWER": "view campaign performance, reports, and analytics",
        "OPERATOR": "manage campaigns, run optimizations, and view reports",
        "ADMIN": "manage team members, configure settings, and oversee operations",
        "OWNER": "full administrative control of your organization's account"
    }
    role_desc = role_descriptions.get(role, "access the platform")

    # Role badge colors
    role_colors = {
        "VIEWER": "#64748b",
        "OPERATOR": "#3b82f6",
        "ADMIN": "#8b5cf6",
        "OWNER": "#f59e0b"
    }
    role_color = role_colors.get(role, BRAND_COLORS['primary'])

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>You're Invited to SADDL AdPulse</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style type="text/css">
        /* Reset styles */
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}

        /* Mobile styles */
        @media only screen and (max-width: 620px) {{
            .email-container {{ width: 100% !important; padding: 20px !important; }}
            .content-padding {{ padding: 24px !important; }}
            .button {{ padding: 14px 32px !important; }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; width: 100%; background-color: {BRAND_COLORS['background']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <!-- Preview text (hidden, shows in inbox) -->
    <div style="display: none; max-height: 0; overflow: hidden;">
        {inviter_name} invited you to join {org_name} on SADDL AdPulse - The Decision-First PPC Platform
    </div>

    <!-- Email wrapper -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: {BRAND_COLORS['background']};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Email container -->
                <table role="presentation" class="email-container" width="600" cellpadding="0" cellspacing="0" style="background-color: {BRAND_COLORS['background_light']}; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">

                    <!-- Header with logo -->
                    <tr>
                        <td class="content-padding" style="padding: 40px 40px 24px 40px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.05);">
                            <!-- Logo SVG inline for better email support -->
                            <div style="margin-bottom: 16px;">
                                <svg width="48" height="48" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" style="display: inline-block;">
                                    <circle cx="32" cy="32" r="30" fill="rgba(37,99,235,0.1)" stroke="url(#grad)" stroke-width="2"/>
                                    <defs>
                                        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                                            <stop offset="0%" style="stop-color:#2563eb;stop-opacity:1" />
                                            <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0.6" />
                                        </linearGradient>
                                    </defs>
                                    <path d="M20 28 Q32 20 44 28" stroke="url(#grad)" stroke-width="2.5" stroke-linecap="round" fill="none"/>
                                    <circle cx="24" cy="32" r="2" fill="#3b82f6"/>
                                    <circle cx="40" cy="32" r="2" fill="#3b82f6"/>
                                    <path d="M22 40 Q32 46 42 40" stroke="url(#grad)" stroke-width="2.5" stroke-linecap="round" fill="none"/>
                                </svg>
                            </div>
                            <h1 style="color: {BRAND_COLORS['text_primary']}; font-size: 24px; font-weight: 700; margin: 0 0 4px 0; letter-spacing: -0.5px;">
                                SADDL AdPulse
                            </h1>
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 13px; margin: 0;">
                                Decision-First PPC Platform
                            </p>
                        </td>
                    </tr>

                    <!-- Main content -->
                    <tr>
                        <td class="content-padding" style="padding: 32px 40px;">
                            <!-- Welcome message -->
                            <h2 style="color: {BRAND_COLORS['text_primary']}; font-size: 28px; font-weight: 600; margin: 0 0 16px 0; line-height: 1.3;">
                                You're Invited!
                            </h2>

                            <p style="color: {BRAND_COLORS['text_secondary']}; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                <strong style="color: {BRAND_COLORS['text_primary']};">{inviter_name}</strong> has invited you to join
                                <strong style="color: {BRAND_COLORS['text_primary']};">{org_name}</strong> on SADDL AdPulse,
                                the decision-first PPC platform that measures actual impact.
                            </p>

                            <!-- Role info box -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
                                <tr>
                                    <td style="background-color: rgba(37,99,235,0.08); border: 1px solid rgba(37,99,235,0.2); border-radius: 12px; padding: 20px;">
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td>
                                                    <p style="color: {BRAND_COLORS['text_muted']}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 8px 0;">
                                                        Your Role
                                                    </p>
                                                    <p style="margin: 0 0 12px 0;">
                                                        <span style="display: inline-block; background-color: {role_color}; color: white; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 6px;">
                                                            {role}
                                                        </span>
                                                    </p>
                                                    <p style="color: {BRAND_COLORS['text_secondary']}; font-size: 14px; line-height: 1.5; margin: 0;">
                                                        As a {role}, you'll be able to {role_desc}.
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
                                <tr>
                                    <td align="center">
                                        <a href="{invitation_url}" class="button" style="display: inline-block; background: linear-gradient(135deg, {BRAND_COLORS['primary']} 0%, {BRAND_COLORS['primary_light']} 100%); color: #ffffff; text-decoration: none; padding: 16px 48px; border-radius: 12px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 16px rgba(37,99,235,0.35); mso-padding-alt: 0;">
                                            <!--[if mso]>
                                            <i style="letter-spacing: 48px; mso-font-width: -100%; mso-text-raise: 30pt;">&nbsp;</i>
                                            <![endif]-->
                                            <span style="mso-text-raise: 15pt;">Accept Invitation</span>
                                            <!--[if mso]>
                                            <i style="letter-spacing: 48px; mso-font-width: -100%;">&nbsp;</i>
                                            <![endif]-->
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Expiry notice -->
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 13px; line-height: 1.5; margin: 0; text-align: center;">
                                This invitation will expire in <strong style="color: {BRAND_COLORS['text_secondary']};">{expiry_days} days</strong>.
                            </p>
                        </td>
                    </tr>

                    <!-- What to expect section -->
                    <tr>
                        <td style="padding: 0 40px 32px 40px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: rgba(255,255,255,0.03); border-radius: 12px; padding: 24px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <p style="color: {BRAND_COLORS['text_primary']}; font-size: 14px; font-weight: 600; margin: 0 0 16px 0;">
                                            What to expect:
                                        </p>
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 0 0 12px 0;">
                                                    <table role="presentation" cellpadding="0" cellspacing="0">
                                                        <tr>
                                                            <td style="vertical-align: top; padding-right: 12px;">
                                                                <span style="color: {BRAND_COLORS['success']}; font-size: 16px;">1.</span>
                                                            </td>
                                                            <td style="color: {BRAND_COLORS['text_secondary']}; font-size: 14px; line-height: 1.5;">
                                                                Click the button above to set up your account
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 0 0 12px 0;">
                                                    <table role="presentation" cellpadding="0" cellspacing="0">
                                                        <tr>
                                                            <td style="vertical-align: top; padding-right: 12px;">
                                                                <span style="color: {BRAND_COLORS['success']}; font-size: 16px;">2.</span>
                                                            </td>
                                                            <td style="color: {BRAND_COLORS['text_secondary']}; font-size: 14px; line-height: 1.5;">
                                                                Create a secure password for your account
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td>
                                                    <table role="presentation" cellpadding="0" cellspacing="0">
                                                        <tr>
                                                            <td style="vertical-align: top; padding-right: 12px;">
                                                                <span style="color: {BRAND_COLORS['success']}; font-size: 16px;">3.</span>
                                                            </td>
                                                            <td style="color: {BRAND_COLORS['text_secondary']}; font-size: 14px; line-height: 1.5;">
                                                                Get a quick tour and start exploring
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 12px; line-height: 1.5; margin: 0 0 8px 0;">
                                If you didn't expect this invitation, you can safely ignore this email.
                            </p>
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 12px; margin: 0;">
                                SADDL AdPulse &bull; Decision-First PPC Platform
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
# PASSWORD RESET EMAIL TEMPLATE
# ============================================================================

def get_password_reset_email_template(
    temp_password: str,
    user_name: Optional[str] = None
) -> str:
    """
    Generate the password reset email HTML.

    Args:
        temp_password: The temporary password generated for the user
        user_name: Optional user's name for personalization

    Returns:
        Complete HTML email string
    """
    greeting = f"Hi {user_name}," if user_name else "Hello,"

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset - SADDL AdPulse</title>
</head>
<body style="margin: 0; padding: 0; width: 100%; background-color: {BRAND_COLORS['background']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: {BRAND_COLORS['background']};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color: {BRAND_COLORS['background_light']}; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 24px 40px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.05);">
                            <h1 style="color: {BRAND_COLORS['text_primary']}; font-size: 24px; font-weight: 700; margin: 0;">
                                SADDL AdPulse
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px 40px;">
                            <h2 style="color: {BRAND_COLORS['text_primary']}; font-size: 24px; font-weight: 600; margin: 0 0 16px 0;">
                                Password Reset
                            </h2>

                            <p style="color: {BRAND_COLORS['text_secondary']}; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                {greeting}
                            </p>

                            <p style="color: {BRAND_COLORS['text_secondary']}; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Your password has been reset. Here is your temporary password:
                            </p>

                            <!-- Temp password box -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
                                <tr>
                                    <td align="center">
                                        <div style="display: inline-block; background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 16px 32px;">
                                            <code style="color: {BRAND_COLORS['text_primary']}; font-size: 20px; font-weight: 600; font-family: 'SF Mono', Consolas, monospace; letter-spacing: 1px;">
                                                {temp_password}
                                            </code>
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <p style="color: {BRAND_COLORS['warning']}; font-size: 14px; line-height: 1.5; margin: 0 0 16px 0; text-align: center;">
                                ⚠️ You will be required to change this password on your next login.
                            </p>

                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 13px; line-height: 1.5; margin: 0; text-align: center;">
                                If you did not request this password reset, please contact your administrator immediately.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 12px; margin: 0;">
                                SADDL AdPulse &bull; Decision-First PPC Platform
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
# WELCOME EMAIL TEMPLATE (Post-Registration)
# ============================================================================

def get_welcome_email_template(
    user_name: str,
    org_name: str,
    login_url: str
) -> str:
    """
    Generate the welcome email HTML sent after successful registration.

    Args:
        user_name: The new user's name
        org_name: Organization name
        login_url: URL to the login page

    Returns:
        Complete HTML email string
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to SADDL AdPulse</title>
</head>
<body style="margin: 0; padding: 0; width: 100%; background-color: {BRAND_COLORS['background']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: {BRAND_COLORS['background']};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color: {BRAND_COLORS['background_light']}; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 24px 40px; text-align: center;">
                            <h1 style="color: {BRAND_COLORS['text_primary']}; font-size: 24px; font-weight: 700; margin: 0 0 8px 0;">
                                Welcome to SADDL AdPulse!
                            </h1>
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 14px; margin: 0;">
                                Your account is ready
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 24px 40px 32px 40px;">
                            <p style="color: {BRAND_COLORS['text_secondary']}; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Hi {user_name},
                            </p>

                            <p style="color: {BRAND_COLORS['text_secondary']}; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Welcome to <strong style="color: {BRAND_COLORS['text_primary']};">{org_name}</strong> on SADDL AdPulse!
                                Your account has been successfully created and you're ready to start exploring.
                            </p>

                            <!-- Features highlight -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
                                <tr>
                                    <td style="background-color: rgba(255,255,255,0.03); border-radius: 12px; padding: 24px;">
                                        <p style="color: {BRAND_COLORS['text_primary']}; font-size: 14px; font-weight: 600; margin: 0 0 16px 0;">
                                            Here's what you can do:
                                        </p>
                                        <ul style="color: {BRAND_COLORS['text_secondary']}; font-size: 14px; line-height: 1.8; margin: 0; padding-left: 20px;">
                                            <li>View the Decision Cockpit for campaign insights</li>
                                            <li>Analyze Impact Waterfalls to see what's working</li>
                                            <li>Run optimizations with transparent attribution</li>
                                            <li>Track verified ROI across your campaigns</li>
                                        </ul>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center">
                                        <a href="{login_url}" style="display: inline-block; background: linear-gradient(135deg, {BRAND_COLORS['primary']} 0%, {BRAND_COLORS['primary_light']} 100%); color: #ffffff; text-decoration: none; padding: 16px 48px; border-radius: 12px; font-size: 16px; font-weight: 600;">
                                            Go to Dashboard
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
                            <p style="color: {BRAND_COLORS['text_muted']}; font-size: 12px; margin: 0;">
                                SADDL AdPulse &bull; Decision-First PPC Platform
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
# TESTING
# ============================================================================

if __name__ == "__main__":
    """Test email template generation."""
    print("Generating sample invitation email...")

    html = get_invitation_email_template(
        inviter_name="John Admin",
        org_name="Acme Corporation",
        role="OPERATOR",
        invitation_url="http://localhost:8501/accept-invite?token=test123",
        expiry_days=7
    )

    # Save to file for preview
    with open("/tmp/invitation_email_preview.html", "w") as f:
        f.write(html)

    print(f"Email template generated ({len(html)} chars)")
    print("Preview saved to: /tmp/invitation_email_preview.html")
