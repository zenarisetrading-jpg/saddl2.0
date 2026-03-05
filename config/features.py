"""
Feature Flags Module for SADDL AdPulse

Centralized feature flag management for gradual rollout of new features.
All flags default to safe values (minimal change to existing behavior).

Usage:
    from config.features import FeatureFlags, FEATURE_EMAIL_INVITATIONS

    if FEATURE_EMAIL_INVITATIONS:
        # Use new email invitation flow
    else:
        # Use legacy manual password flow

    # Or check dynamically:
    if FeatureFlags.is_enabled('ENABLE_EMAIL_INVITATIONS'):
        ...
"""

import os
from pathlib import Path
from typing import Dict, Optional
from functools import lru_cache

# Load environment variables from multiple locations (matching main app pattern)
try:
    from dotenv import load_dotenv
    current_dir = Path(__file__).parent.parent  # Go up from config/ to desktop/
    load_dotenv(current_dir / '.env')           # desktop/.env
    load_dotenv(current_dir.parent / '.env')    # saddle/.env (parent directory)
except ImportError:
    pass


class FeatureFlags:
    """
    Centralized feature flag management.

    Reads flags from environment variables with safe defaults.
    Provides both static and dynamic flag checking.
    """

    # Default values for all feature flags
    # These are used when env vars are not set
    DEFAULTS: Dict[str, bool] = {
        'ENABLE_EMAIL_INVITATIONS': True,       # Phase 1: Email invites (Enabled)
        'ENABLE_ONBOARDING_WIZARD': True,       # Phase 3: Welcome wizard (Enabled)
        'ENABLE_ENHANCED_EMPTY_STATES': True,   # Phase 4: Styled empty states
        # Performance Dashboard rollout flags (all OFF by default until validated)
        'ENABLE_PERFORMANCE_DASHBOARD_BUSINESS_OVERVIEW': False,
        'ENABLE_PERFORMANCE_DASHBOARD_PRODUCT': False,
        'ENABLE_PERFORMANCE_DASHBOARD_INVENTORY_OVERVIEW': False,
        'ENABLE_PERFORMANCE_DASHBOARD_INTELLIGENCE': False,
        'ENABLE_PERFORMANCE_DASHBOARD_PPC_OVERVIEW': True,
        # Phase 0 deprecation flags — OFF = legacy tab hidden, ON = legacy tab visible
        'ENABLE_ACCOUNT_OVERVIEW_LEGACY': False,
        'ENABLE_DIAGNOSTICS_LEGACY': False,
    }

    @staticmethod
    def is_enabled(flag_name: str) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Name of the flag (e.g., 'ENABLE_EMAIL_INVITATIONS')

        Returns:
            True if flag is enabled, False otherwise

        Notes:
            - Reads from environment variable
            - Falls back to DEFAULTS if not set
            - Case-insensitive value comparison ('true', 'True', 'TRUE' all work)
        """
        default = FeatureFlags.DEFAULTS.get(flag_name, False)
        value = os.getenv(flag_name, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')

    @staticmethod
    def get_all_flags() -> Dict[str, bool]:
        """
        Get status of all known feature flags.

        Returns:
            Dictionary mapping flag names to their current boolean values

        Useful for:
            - Admin dashboard display
            - Debugging
            - Logging current configuration
        """
        return {
            'email_invitations': FeatureFlags.is_enabled('ENABLE_EMAIL_INVITATIONS'),
            'onboarding_wizard': FeatureFlags.is_enabled('ENABLE_ONBOARDING_WIZARD'),
            'enhanced_empty_states': FeatureFlags.is_enabled('ENABLE_ENHANCED_EMPTY_STATES'),
            'perf_dashboard_business_overview': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_BUSINESS_OVERVIEW'),
            'perf_dashboard_product': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_PRODUCT'),
            'perf_dashboard_inventory_overview': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_INVENTORY_OVERVIEW'),
            'perf_dashboard_intelligence': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_INTELLIGENCE'),
            'perf_dashboard_ppc_overview': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_PPC_OVERVIEW'),
        }

    @staticmethod
    def get_flag_info() -> Dict[str, Dict]:
        """
        Get detailed information about all feature flags.

        Returns:
            Dictionary with flag details including:
            - current value
            - default value
            - description
            - phase

        Useful for admin UI display.
        """
        return {
            'ENABLE_EMAIL_INVITATIONS': {
                'value': FeatureFlags.is_enabled('ENABLE_EMAIL_INVITATIONS'),
                'default': False,
                'description': 'Email invitations with secure links',
                'phase': 'Phase 1',
                'risk': 'low',
            },
            'ENABLE_ONBOARDING_WIZARD': {
                'value': FeatureFlags.is_enabled('ENABLE_ONBOARDING_WIZARD'),
                'default': False,
                'description': '3-step welcome wizard for new users',
                'phase': 'Phase 3',
                'risk': 'low',
            },
            'ENABLE_ENHANCED_EMPTY_STATES': {
                'value': FeatureFlags.is_enabled('ENABLE_ENHANCED_EMPTY_STATES'),
                'default': True,
                'description': 'Styled empty state guidance',
                'phase': 'Phase 4',
                'risk': 'minimal',
            },
            'ENABLE_PERFORMANCE_DASHBOARD_BUSINESS_OVERVIEW': {
                'value': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_BUSINESS_OVERVIEW'),
                'default': False,
                'description': 'Performance Dashboard: Business Overview tab',
                'phase': 'Performance Dashboard',
                'risk': 'medium',
            },
            'ENABLE_PERFORMANCE_DASHBOARD_PRODUCT': {
                'value': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_PRODUCT'),
                'default': False,
                'description': 'Performance Dashboard: Product tab',
                'phase': 'Performance Dashboard',
                'risk': 'medium',
            },
            'ENABLE_PERFORMANCE_DASHBOARD_INVENTORY_OVERVIEW': {
                'value': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_INVENTORY_OVERVIEW'),
                'default': False,
                'description': 'Performance Dashboard: Inventory Overview tab',
                'phase': 'Performance Dashboard',
                'risk': 'medium',
            },
            'ENABLE_PERFORMANCE_DASHBOARD_INTELLIGENCE': {
                'value': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_INTELLIGENCE'),
                'default': False,
                'description': 'Performance Dashboard: Intelligence tab',
                'phase': 'Performance Dashboard',
                'risk': 'medium',
            },
            'ENABLE_PERFORMANCE_DASHBOARD_PPC_OVERVIEW': {
                'value': FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_PPC_OVERVIEW'),
                'default': False,
                'description': 'Performance Dashboard: PPC Overview tab',
                'phase': 'Performance Dashboard',
                'risk': 'medium',
            },
        }

    @staticmethod
    def log_current_state() -> str:
        """
        Generate a log-friendly string of current flag states.

        Returns:
            Formatted string showing all flags and their values
        """
        flags = FeatureFlags.get_all_flags()
        lines = ["Feature Flags Status:"]
        for name, enabled in flags.items():
            status = "ENABLED" if enabled else "disabled"
            lines.append(f"  - {name}: {status}")
        return "\n".join(lines)


# ============================================================================
# CONVENIENCE CONSTANTS
# ============================================================================
# Import these directly for cleaner code:
#   from config.features import FEATURE_EMAIL_INVITATIONS
#
# These are evaluated at module load time, so they won't change during runtime.
# If you need dynamic checking (e.g., for hot-reload), use FeatureFlags.is_enabled()

FEATURE_EMAIL_INVITATIONS = FeatureFlags.is_enabled('ENABLE_EMAIL_INVITATIONS')
FEATURE_ONBOARDING_WIZARD = FeatureFlags.is_enabled('ENABLE_ONBOARDING_WIZARD')
FEATURE_ENHANCED_EMPTY_STATES = FeatureFlags.is_enabled('ENABLE_ENHANCED_EMPTY_STATES')
FEATURE_PERF_DASH_BUSINESS_OVERVIEW = FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_BUSINESS_OVERVIEW')
FEATURE_PERF_DASH_PRODUCT = FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_PRODUCT')
FEATURE_PERF_DASH_INVENTORY_OVERVIEW = FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_INVENTORY_OVERVIEW')
FEATURE_PERF_DASH_INTELLIGENCE = FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_INTELLIGENCE')
FEATURE_PERF_DASH_PPC_OVERVIEW = FeatureFlags.is_enabled('ENABLE_PERFORMANCE_DASHBOARD_PPC_OVERVIEW')
FEATURE_ACCOUNT_OVERVIEW_LEGACY = FeatureFlags.is_enabled('ENABLE_ACCOUNT_OVERVIEW_LEGACY')
FEATURE_DIAGNOSTICS_LEGACY = FeatureFlags.is_enabled('ENABLE_DIAGNOSTICS_LEGACY')


def is_performance_dashboard_tab_enabled(tab_key: str) -> bool:
    """Check if a given performance dashboard tab is enabled."""
    mapping = {
        'business_overview': 'ENABLE_PERFORMANCE_DASHBOARD_BUSINESS_OVERVIEW',
        'product': 'ENABLE_PERFORMANCE_DASHBOARD_PRODUCT',
        'inventory_overview': 'ENABLE_PERFORMANCE_DASHBOARD_INVENTORY_OVERVIEW',
        'intelligence': 'ENABLE_PERFORMANCE_DASHBOARD_INTELLIGENCE',
        'ppc_overview': 'ENABLE_PERFORMANCE_DASHBOARD_PPC_OVERVIEW',
    }
    env_name = mapping.get(tab_key)
    if not env_name:
        return False
    return FeatureFlags.is_enabled(env_name)


# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
# These are not feature flags, but commonly needed settings

@lru_cache(maxsize=1)
def get_app_url() -> str:
    """
    Get the base application URL.

    Used for constructing invitation links, password reset links, etc.
    Cached for performance.
    """
    return os.getenv('APP_URL', 'http://localhost:8501')


@lru_cache(maxsize=1)
def get_invitation_expiry_days() -> int:
    """
    Get the invitation token expiry period in days.

    Default: 7 days
    """
    try:
        return int(os.getenv('INVITATION_EXPIRY_DAYS', '7'))
    except ValueError:
        return 7


def get_password_requirements() -> Dict[str, any]:
    """
    Get password validation requirements.

    Returns:
        Dictionary with password rules
    """
    return {
        'min_length': int(os.getenv('PASSWORD_MIN_LENGTH', '8')),
        'require_uppercase': os.getenv('PASSWORD_REQUIRE_UPPERCASE', 'true').lower() == 'true',
        'require_lowercase': os.getenv('PASSWORD_REQUIRE_LOWERCASE', 'true').lower() == 'true',
        'require_number': os.getenv('PASSWORD_REQUIRE_NUMBER', 'true').lower() == 'true',
    }


# ============================================================================
# DEBUG HELPERS
# ============================================================================

if __name__ == '__main__':
    # Run this file directly to check current flag status
    print(FeatureFlags.log_current_state())
    print(f"\nApp URL: {get_app_url()}")
    print(f"Invitation Expiry: {get_invitation_expiry_days()} days")
    print(f"Password Requirements: {get_password_requirements()}")
