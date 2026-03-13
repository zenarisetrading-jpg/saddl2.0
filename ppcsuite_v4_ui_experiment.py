import streamlit as st

st.markdown(
    '<meta http-equiv="refresh" content="0; url=https://dashboard.saddl.io">',
    unsafe_allow_html=True,
)
st.stop()

import sys
import os
from pathlib import Path

# Add current directory to path to fix imports on Cloud
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# ==========================================

# ==========================================
# PAGE CONFIGURATION (Must be very first ST command)
# ==========================================
st.set_page_config(
    page_title="Saddle AdPulse",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

import pandas as pd
from datetime import datetime
import os

# BRIDGE: Load Environment Variables (support .env in desktop/ or parent root)
try:
    from dotenv import load_dotenv
    current_dir = Path(__file__).parent
    load_dotenv(current_dir / '.env')          # desktop/.env
    load_dotenv(current_dir.parent / '.env')   # saddle/.env
except ImportError:
    pass

# BRIDGE: Load Streamlit Secrets into OS Environment for Core Modules
try:
    if "DATABASE_URL" in st.secrets:
        os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
except FileNotFoundError:
    pass 

# === SEEDING (CRITICAL FOR STREAMLIT CLOUD) ===
# Run seeding with @st.cache_resource to execute only once per app instance
# This prevents connection pool exhaustion from concurrent seeding attempts
# MOVED TO LAZY EXECUTION: Now runs in main() BEFORE login check, not at module load time
@st.cache_resource(show_spinner=False)  # Cache forever - seeding only needs to run once per deployment
def run_seeding():
    # Skip seeding if explicitly disabled via environment variable
    # NOTE: Seeding disabled by default on Streamlit Cloud to prevent hanging
    if os.getenv("SKIP_SEEDING") == "true":
        print("SEED: Skipping (SKIP_SEEDING=true)")
        return "Seeding skipped"

    try:
        from app_core.seeding import seed_initial_data
        # Simple execution - no timeout handling to avoid signal/threading issues
        result = seed_initial_data()
        return result or "Seeding completed"

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Startup Seeding Failed: {e}")
        return f"Seeding failed: {e}"

# Seeding will be called lazily in main() to avoid blocking module import

# Delay heavy feature imports by moving them into routing/main logic


# Delay heavy feature imports by moving them into routing/main logic
from ui.layout import setup_page, render_sidebar, render_home
from app_core.data_hub import DataHub
from app_core.db_manager import get_db_manager
from utils.matchers import ExactMatcher
from utils.formatters import format_currency
from app_core.data_loader import safe_numeric
from app_core.session_state import init_session_state
from pathlib import Path

# === ONBOARDING ===
from ui.onboarding import should_show_onboarding, render_onboarding_wizard
from config.features import FEATURE_ONBOARDING_WIZARD
from config.features import FeatureFlags

# === AUTHENTICATION ===
from app_core.auth.service import AuthService
from app_core.auth.middleware import require_auth, require_permission
from ui.auth.login import render_login
# Legacy import removed: from auth import require_authentication, render_user_menu

# ── PostgreSQL enforcement ──────────────────────────────────────────────────
import sys as _sys
_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url.startswith("postgresql"):
    print("ERROR: SADDL requires a PostgreSQL connection. SQLite is not supported.")
    _sys.exit(1)
# ────────────────────────────────────────────────────────────────────────────

# Global dark theme CSS for sidebar buttons
st.markdown("""
<style>
/* Fix sidebar buttons in dark mode */
[data-testid="stSidebar"] .stButton > button {
    background-color: rgba(30, 41, 59, 0.8) !important;
    color: white !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: rgba(51, 65, 85, 0.9) !important;
    border-color: rgba(255, 255, 255, 0.2) !important;
}
/* Download buttons */
.stDownloadButton > button {
    background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
    color: white !important;
    border: none !important;
}

/* Dark mode/Test mode toggle overrides */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #F5F5F7 !important;
    font-weight: 500 !important;
}
/* Toggle Switch Background when Checked */
[data-testid="stSidebar"] div[data-testid="stCheckbox"] > label > div[role="switch"][aria-checked="true"] {
    background-color: #5B556F !important;
}
/* Radio Button Outer Circle when active */
[data-testid="stSidebar"] div[data-testid="stRadio"] label div:first-child[data-baseweb="radio"] > div:first-child {
    border-color: #5B556F !important;
}
/* Radio Button Inner Dot when checked */
[data-testid="stSidebar"] div[data-testid="stRadio"] label div:first-child[data-baseweb="radio"] > div:first-child > div {
    background-color: #5B556F !important;
}

/* Print Mode: Hide sidebar and UI elements when printing */
@media print {
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stHeader"] { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    .stDeployButton { display: none !important; }
    .stDownloadButton { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    header { display: none !important; }
    .main .block-container { padding: 1rem !important; max-width: 100% !important; }
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_module' not in st.session_state:
    st.session_state['current_module'] = 'home'

if 'test_mode' not in st.session_state:
    st.session_state['test_mode'] = False

if 'db_manager' not in st.session_state:
    st.session_state['db_manager'] = None

if "active_perf_tab" not in st.session_state:
    st.session_state["active_perf_tab"] = "overview"


# ==========================================
# PERFORMANCE HUB (Snapshot + Report Card)
# ==========================================
# ==========================================
# PERFORMANCE HUB (Snapshot + Report Card)
# ==========================================
def run_performance_hub():
    """Consolidated Account Overview + Report Card."""
    # Force empty state for testing
    if st.query_params.get("test_state") == "no_data":
        from ui.components.empty_states import render_empty_state
        account = st.session_state.get('active_account_name', 'Account')
        render_empty_state('no_data', context={'account_name': account})
        return

    # === TAB NAVIGATION (Premium Button Style) ===
    st.markdown("""
    <style>
    /* Premium Tab Buttons */
    div[data-testid="stHorizontalBlock"] div.stButton > button {
        background: rgba(143, 140, 163, 0.05) !important;
        border: 1px solid rgba(143, 140, 163, 0.15) !important;
        color: #8F8CA3 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        padding: 8px 16px !important;
    }
    div[data-testid="stHorizontalBlock"] div.stButton > button:hover {
        background: rgba(143, 140, 163, 0.1) !important;
        border-color: rgba(91, 85, 111, 0.3) !important;
        color: #F5F5F7 !important;
    }
    /* Active Tab Styling - Using Primary kind */
    div[data-testid="stHorizontalBlock"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #5B556F 0%, #464156 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #F5F5F7 !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Always use the current Account Overview experience in cloud:
    # Business Overview + PPC Overview tabs.
    # Legacy Client Report remains optional and hidden by default.
    if True:
        _show_ppc_tab = True
        _show_legacy_tab = False

        if "active_perf_tab" not in st.session_state:
            st.session_state["active_perf_tab"] = "Business Overview"

        # If legacy tab is disabled and it was previously selected, reset to Business Overview
        if not _show_legacy_tab and st.session_state.get("active_perf_tab") == "Client Report":
            st.session_state["active_perf_tab"] = "Business Overview"

        _num_tabs = 1 + int(_show_ppc_tab) + int(_show_legacy_tab)
        _tab_cols = st.columns(_num_tabs)
        _col_idx = 0
        with _tab_cols[_col_idx]:
            if st.button(
                "BUSINESS OVERVIEW",
                key="btn_business_overview",
                use_container_width=True,
                type="primary" if st.session_state["active_perf_tab"] == "Business Overview" else "secondary",
            ):
                st.session_state["_nav_loading"] = True
                st.session_state["active_perf_tab"] = "Business Overview"
                st.rerun()
        _col_idx += 1
        if _show_legacy_tab:
            with _tab_cols[_col_idx]:
                if st.button(
                    "ACCOUNT OVERVIEW (LEGACY)",
                    key="btn_account_overview_legacy",
                    use_container_width=True,
                    type="primary" if st.session_state["active_perf_tab"] == "Client Report" else "secondary",
                ):
                    st.session_state["_nav_loading"] = True
                    st.session_state["active_perf_tab"] = "Client Report"
                    st.rerun()
            _col_idx += 1
        if _show_ppc_tab:
            with _tab_cols[_col_idx]:
                if st.button(
                    "PPC OVERVIEW",
                    key="btn_ppc_overview",
                    use_container_width=True,
                    type="primary" if st.session_state["active_perf_tab"] == "PPC Overview" else "secondary",
                ):
                    st.session_state["_nav_loading"] = True
                    st.session_state["active_perf_tab"] = "PPC Overview"
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state["active_perf_tab"] == "Business Overview":
            from features.dashboard.business_overview import render_business_overview
            render_business_overview()
        elif _show_ppc_tab and st.session_state["active_perf_tab"] == "PPC Overview":
            from ui.performance_dashboard.ppc_overview import render_ppc_overview
            render_ppc_overview()
        elif _show_legacy_tab and st.session_state["active_perf_tab"] == "Client Report":
            import ui.client_report_page as client_report
            import importlib
            importlib.reload(client_report)
            client_report.run()
        else:
            # Fallback: always show Business Overview when legacy is disabled
            from features.dashboard.business_overview import render_business_overview
            render_business_overview()
        return

    # Should never reach legacy fallback path above.
    return


def run_diagnostics_hub():
    """Diagnostics Control Center v2.0."""
    from features.diagnostics.control_center import render_control_center
    
    # Retrieve client ID (support both new primitive key and old dict legacy)
    client_id = st.session_state.get('active_account_id')
    if not client_id:
        # Fallback to legacy dictionary if present
        client_id = st.session_state.get('active_account', {}).get('account_id', 's2c_uae_test')
        
    render_control_center(client_id)


# ==========================================
# CONSOLIDATED V4 OPTIMIZER
# ==========================================
def run_consolidated_optimizer():
    """Execution logic: Optimizer + ASIN Mapper + AI Insights all in one view."""
    
    # Force empty state for testing
    if st.query_params.get("test_state") == "no_data":
        from ui.components.empty_states import render_empty_state
        account = st.session_state.get('active_account_name', 'Account')
        render_empty_state('no_data', context={'account_name': account})
        return

    # Flag to skip execution while still rendering widgets (preserves settings during dialog)
    skip_execution = st.session_state.get('_show_action_confirmation', False)
    
    # === OPTIMIZER V2 (REFACTORED) ===
    # User Request: "deprecate the optimizer legacy dashboard... remove all the wiring"
    # We now exclusively run the Refactored V2 Optimizer
    
    from features.optimizer_v2.main import render_optimizer_v2
    render_optimizer_v2()
    return  # Stop execution here - do not run legacy code below

# ==========================================
# MAIN ROUTER
# ==========================================

def render_shared_report():
    """
    Render read-only shared report view.
    Route: ?page=shared_report&id={report_id}
    """
    import streamlit as st
    from app_core.db_manager import get_db_manager
    from ui import client_report_page as client_report
    
    # Get report ID from URL
    query_params = st.query_params
    report_id = query_params.get("id")
    
    if not report_id:
        st.error("⚠️ **Invalid Share Link**")
        st.info("This link appears to be incomplete. Please check the URL and try again.")
        st.stop()
    
    try:
        # Fetch report from database
        db = get_db_manager()
        report_data = db.get_shared_report(report_id)
        
        # Set session state for report context
        st.session_state['active_account_id'] = report_data['client_id']
        st.session_state['date_range'] = report_data['date_range']
        st.session_state['read_only_mode'] = True
        st.session_state['show_client_report'] = True  # Bypass landing page
        
        # Hydrate AI Narratives (if they exist)
        narratives = report_data.get('metadata', {}).get('narratives', {})
        if narratives:
             cache_key = f"client_report_narratives_{report_data['client_id']}"
             st.session_state[cache_key] = narratives
        
        # Show view counter badge
        views = report_data.get('views', 1)
        if views > 1:
            st.caption(f"👁️ This report has been viewed **{views} times**")
        
        # Render report (same page, read-only mode)
        client_report.run()
        
    except ValueError as e:
        # Report not found or expired
        error_msg = str(e)
        
        st.error(f"⚠️ **{error_msg}**")
        
        if "expired" in error_msg.lower():
            st.info("💡 **Shared reports expire after 30 days.** Please contact the report sender for a new link.")
        elif "not found" in error_msg.lower():
            st.info("💡 **This report may have been deleted or the link is incorrect.** Please verify the URL.")
        else:
            st.info("💡 **Unable to load report.** Please contact the report sender for assistance.")
        
        st.stop()
        
    except Exception as e:
        st.error(f"❌ **Error loading report:** {str(e)}")
        st.info("Please try refreshing the page. If the issue persists, contact support.")
        st.stop()


# ==========================================
# MAIN ROUTER
# ==========================================
def main():
    # Initialize all session state keys with safe defaults before any logic runs.
    # This eliminates the entire class of KeyError crashes permanently.
    init_session_state()

    # === SHARED REPORT ROUTE (Public/No Auth) ===
    # Must be first to bypass auth
    query_params = st.query_params
    if query_params.get("page") == "shared_report":
        render_shared_report()
        return

    setup_page()

    # === FORCE SIDEBAR STATE TO EXPANDED ===
    # Reset sidebar state in session to force it expanded
    # Check multiple possible session state keys that Streamlit uses internally
    for key in ['_sidebar_state', 'sidebar_state', '_main_menu_visibility']:
        if key in st.session_state:
            if key == '_main_menu_visibility':
                st.session_state[key] = 'hidden'
            else:
                st.session_state[key] = 'expanded'

    # === LOCK SIDEBAR OPEN & HIDE HEADER ===
    # CSS-only approach that runs before authentication
    # JavaScript will be injected AFTER authentication to avoid interfering with login
    st.markdown("""
    <style>
        /* CRITICAL: Hide ALL sidebar collapse controls */
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[kind="header"][data-testid="baseButton-header"],
        button[kind="headerNoPadding"],
        section[data-testid="stSidebar"] button[kind="header"],
        section[data-testid="stSidebar"] > div > button[kind="header"] {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
            opacity: 0 !important;
            width: 0 !important;
            height: 0 !important;
        }

        /* Force sidebar to ALWAYS be visible and expanded */
        section[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
            position: relative !important;
            min-width: 244px !important;
            max-width: 244px !important;
            width: 244px !important;
            transform: translateX(0) !important;
            transition: none !important;
        }

        /* Override ANY collapsed state styling */
        section[data-testid="stSidebar"][aria-expanded="false"],
        section[data-testid="stSidebar"].collapsed,
        section[data-testid="stSidebar"][data-collapsed="true"] {
            display: block !important;
            visibility: visible !important;
            min-width: 244px !important;
            max-width: 244px !important;
            width: 244px !important;
            transform: translateX(0) !important;
        }

        /* Ensure sidebar content is visible */
        section[data-testid="stSidebar"] > div {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
        }

        /* Hide the main header, toolbar, and decoration */
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        .stApp > header {
            visibility: hidden !important;
            height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            display: none !important;
        }

        /* Hide the deploy button specifically */
        .stDeployButton,
        [data-testid="stStatusWidget"] {
            display: none !important;
        }

        /* Hide the footer and "Made with Streamlit" */
        footer,
        footer[data-testid="stFooter"] {
            visibility: hidden !important;
            display: none !important;
        }

        /* Adjust top padding since header is gone */
        .main .block-container {
            padding-top: 1rem !important;
        }
    </style>
    """, unsafe_allow_html=True)



    # === AUTHENTICATION GATE ===
    # Shows login page if not authenticated, blocks access to main app
    # === AUTHENTICATION GATE (V2) ===
    # Using strict V2 Auth Service with Type Assertion
    from app_core.auth.models import User
    from app_core.auth.service import AuthService  # Explicit local import to guarantee scope
    from app_core.auth.permissions import has_permission, has_permission_for_account
    
    auth_service = AuthService()
    user = auth_service.get_current_user() # Gets from session
    
    # === AMAZON OAUTH CALLBACK INTERCEPTION ===
    # Check if we are returning from the Amazon LWA OAuth flow (via Supabase Edge Function)
    query_params = st.query_params
    if query_params.get("amazon_auth") == "success":
        connected_client_id = query_params.get("client_id")
        if connected_client_id:
            st.session_state['amazon_connected'] = True
            st.session_state['amazon_client_id'] = connected_client_id
            st.toast("✅ Successfully connected to Amazon Ads!")
        
        # Clear the params so a refresh doesn't trigger it again
        st.query_params.clear()
        
    elif query_params.get("amazon_auth") == "failed":
        reason = query_params.get("reason", "Unknown error")
        st.error(f"Failed to connect to Amazon Ads: {reason}")
        st.query_params.clear()

    if user is None:
        # === RUN SEEDING BEFORE LOGIN ===
        # Database must be initialized for login to work
        # Only runs once per app instance (cached)
        # Show a friendly message while initializing
        try:
            import time
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

            # Run seeding with timeout to prevent infinite hang
            with st.spinner("Initializing database..."):
                start_time = time.time()
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(run_seeding)

                try:
                    seeding_result = future.result(timeout=10.0)
                    elapsed = time.time() - start_time
                    print(f"SEED: Completed in {elapsed:.2f}s")

                    if seeding_result and "Error" in str(seeding_result):
                        st.warning(f"⚠️ Database initialization had issues: {seeding_result}")
                        st.info("You may still be able to log in if the database was previously initialized.")
                except FuturesTimeoutError:
                    # Do not block startup waiting for a stuck worker thread.
                    future.cancel()
                    st.warning("⚠️ Database initialization is taking too long.")
                    st.info("Continuing to login. If sign-in fails, check DATABASE_URL and database reachability.")
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            st.error(f"❌ Database initialization failed: {e}")
            st.info("If the database was already initialized, you can proceed to login.")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

        # Not logged in? Show V2 login screen and stop
        render_login()
        st.stop()

    # STRICT TYPE ASSERTION (Guardrail)
    if not isinstance(user, User):
        # This catches session corruption or mixing legacy/v2 usage
        auth_service.sign_out()
        st.error("Session type mismatch. Please refresh and login again.")
        st.stop()

    # === PHASE 3: ONBOARDING WIZARD ===
    # Show wizard for new users who haven't completed onboarding
    # Must come AFTER authentication but BEFORE any main content
    if FEATURE_ONBOARDING_WIZARD and should_show_onboarding():
        render_onboarding_wizard()
        st.stop()  # Don't render main app while wizard is active

    # PHASE 3: FORCED PASSWORD RESET MIDDLEWARE
    if user.must_reset_password:
        # If user must reset, lock them to 'profile' module
        if st.session_state.get('current_module') != 'profile':
            st.session_state['_nav_loading'] = True
            st.session_state['current_module'] = 'profile'
            st.warning("⚠️ You must change your password to proceed.")
            st.rerun()

    # PHASE 3 SECURITY: UPDATE LAST LOGIN
    # We do this here (middleware) to ensure it runs on every fresh session
    # but to avoid DB spam, we only do it if the session is "fresh" (e.g. not updated in last 5 min)
    # simplified: just do it on first load of session
    if 'login_tracked' not in st.session_state:
        try:
             # Quick direct update using manual cursor management for SQLite compatibility
             ph = auth_service.db_manager.placeholder
             with auth_service._get_connection() as conn:
                 cur = conn.cursor()
                 try:
                     # CURRENT_TIMESTAMP is standard SQL (works in PG and SQLite)
                     query = f"UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = {ph}"
                     cur.execute(query, (str(user.id),))
                 finally:
                     cur.close()
             st.session_state['login_tracked'] = True
        except Exception as e:
            print(f"Login Track Error: {e}")

    # User is valid V2 user - proceed

    # === DATABASE INITIALIZATION ===

    # Initialize db_manager right after auth, before any UI that needs it
    if st.session_state.get('db_manager') is None:
        st.session_state['db_manager'] = get_db_manager(st.session_state.get('test_mode', False))

    # Phase 3.5: Set Account Context for Permissions
    # Must be done after DB init/loading where active_account_id is derived
    acc_ctx = None
    if 'active_account_id' in st.session_state:
        from uuid import UUID
        try:
            acc_ctx = UUID(str(st.session_state['active_account_id']))
        except:
            pass
    st.session_state['permission_account_context'] = acc_ctx
    
    # === TOP-RIGHT HEADER (Profile, Account, Logout) ===
    # This renders a fixed-position header component
    # Legacy: render_user_menu() -> Removed in V2 (Logout in sidebar)
    
    # Helper: Safe navigation (checks for pending actions when leaving optimizer)
    # Helper: Navigation
    def safe_navigate(target_module):
        st.session_state['_nav_loading'] = True
        st.session_state['current_module'] = target_module
        st.rerun()
    
    # Simplified V4 Sidebar
    with st.sidebar:
        # Sidebar Logo at TOP (theme-aware, prominent)
        import base64
        from pathlib import Path
        theme_mode = st.session_state.get('theme_mode', 'dark')
        logo_filename = "saddle_logo.png" if theme_mode == 'dark' else "saddle_logo_light.png"
        logo_path = Path(__file__).parent / "static" / logo_filename
        
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                logo_data = base64.b64encode(f.read()).decode()
            st.markdown(
                f'<div style="text-align: center; padding: 15px 0 20px 0;"><img src="data:image/png;base64,{logo_data}" style="width: 200px;" /></div>',
                unsafe_allow_html=True
            )
        
        # Account selector (right after logo)
        from ui.account_manager import render_account_selector
        render_account_selector()
        
        # Logout button (compact)
        from app_core.auth.service import AuthService
        auth = AuthService()
        if st.button("⏻ Logout", key="sidebar_logout", use_container_width=True, help="Sign out"):
            auth.sign_out()
            st.rerun()
        
        st.divider()
        
        # =========================
        # PRIMARY NAVIGATION
        # =========================
        # Side Navigation Icons
        nav_icon_color = "#8F8CA3"
        home_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>'
        performance_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 12v5"/><path d="M12 9v8"/><path d="M17 11v6"/></svg>'
        report_card_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>'
        impact_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>'
        diagnostics_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M3 3h7v7H3z"></path><path d="M14 3h7v7h-7z"></path><path d="M14 14h7v7h-7z"></path><path d="M3 14h7v7H3z"></path></svg>'
        check_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="m9 11 3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>'
        rocket_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path><path d="m9 12 2.5 2.5"></path></svg>'
        storage_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M21 20V4a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v16"></path><rect x="3" y="4" width="18" height="4" rx="2"></rect><rect x="3" y="12" width="18" height="4" rx="2"></rect></svg>'
        help_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
        settings_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>'

        # Stylized nav button with CSS injection for hover effects and integrated SVG
        st.markdown(f"""
        <style>
        .nav-chiclet {{
            background: rgba(143, 140, 163, 0.05);
            border: 1px solid rgba(143, 140, 163, 0.1);
            border-radius: 10px;
            padding: 10px 15px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: #B6B4C2;
            text-decoration: none;
        }}
        .nav-chiclet:hover {{
            background: rgba(143, 140, 163, 0.1);
            border-color: rgba(124, 58, 237, 0.4);
            color: #F5F5F7;
            transform: translateX(4px);
        }}
        .nav-chiclet.active {{
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.15) 0%, rgba(124, 58, 237, 0.08) 100%);
            border-color: rgba(124, 58, 237, 0.5);
            color: #F5F5F7;
        }}
        </style>
        """, unsafe_allow_html=True)

        def nav_chiclet_link(label, icon_html, module_key):
            is_active = st.session_state.get('current_module') == module_key
            active_class = "active" if is_active else ""
            
            # Use a transparent button over the chiclet for interactivity
            if st.button(label, key=f"nav_{module_key}", use_container_width=True):
                # Check if leaving optimizer with pending actions
                if st.session_state.get('current_module') == 'optimizer' and st.session_state.get('pending_actions'):
                    # Trigger confirmation dialog instead of navigating
                    st.session_state['_show_action_confirmation'] = True
                    st.session_state['_pending_navigation_target'] = module_key
                    st.rerun()
                else:
                    # Navigate directly
                    st.session_state['_nav_loading'] = True
                    st.session_state['current_module'] = module_key
                    st.rerun()

        # Re-using the nav_button logic but with the chiclet feel properly integrated
        # We'll use Streamlit's native buttons but style them to look like the chiclets
        st.markdown("""
        <style>
        /* Base Sidebar Button Styling - Targets all buttons in our custom wrappers */
        [data-testid="stSidebar"] .nav-item-wrapper div.stButton > button,
        [data-testid="stSidebar"] .sub-nav-wrapper div.stButton > button {
            background: rgba(143, 140, 163, 0.05) !important;
            border: 1px solid rgba(143, 140, 163, 0.1) !important;
            border-radius: 10px !important;
            color: #B6B4C2 !important;
            text-align: left !important;
            padding: 8px 12px !important;
            margin-bottom: 0px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        
        /* Balanced vertical spacing between sidebar elements */
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.5rem !important;
        }
        
        /* Fix the alignment and gap of the icon column */
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;
        }

        /* Balanced Dividers */
        [data-testid="stSidebar"] hr {
            margin: 1rem 0 !important;
            opacity: 0.15 !important;
        }
        
        [data-testid="stSidebar"] .nav-item-wrapper div.stButton > button:hover {
            background: rgba(143, 140, 163, 0.1) !important;
            border-color: rgba(91, 85, 111, 0.4) !important;
            color: #F5F5F7 !important;
            transform: translateX(4px) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Helper for stylized nav buttons with inline SVGs
        def nav_button_chiclet(label, icon_html, key):
            is_active = st.session_state.get('current_module') == key
            active_bg = "linear-gradient(135deg, rgba(91, 85, 111, 0.2) 0%, rgba(91, 85, 111, 0.1) 100%)" if is_active else "rgba(143, 140, 163, 0.05)"
            active_border = "rgba(91, 85, 111, 0.5)" if is_active else "rgba(143, 140, 163, 0.1)"
            
            # Use specific CSS for active button targeting the wrapper
            st.markdown(f"""
            <style>
            .nav-wrapper-{key} div.stButton > button {{
                background: {active_bg} !important;
                border-color: {active_border} !important;
                color: {"#F5F5F7" if is_active else "#B6B4C2"} !important;
            }}
            </style>
            """, unsafe_allow_html=True)

            st.markdown(f'<div class="nav-item-wrapper nav-wrapper-{key}">', unsafe_allow_html=True)
            col1, col2 = st.columns([1, 6])
            with col1:
                st.markdown(f'<div style="margin-top: 5px; margin-left: 5px; opacity: {"1.0" if is_active else "0.6"};">{icon_html}</div>', unsafe_allow_html=True)
            with col2:
                if st.button(label, use_container_width=True, key=f"nav_btn_v6_{key}"):
                    safe_navigate(key)
            st.markdown('</div>', unsafe_allow_html=True)

        nav_button_chiclet("Home", home_icon, "home")
        
        st.divider()
        st.markdown("##### ANALYZE")
        
        # PERMISSION GATING (V2)
        from app_core.auth.permissions import has_permission
        
        nav_button_chiclet("Account Overview", performance_icon, "performance")
        
        # Optimizer - Requires 'run_optimizer'
        # Phase 3.5: Operator cannot run optimizer if overridden to VIEWER on this account
        if has_permission_for_account(user, 'run_optimizer', st.session_state.get('permission_account_context')):
            nav_button_chiclet("Optimizer", check_icon, "optimizer")
            
        if FeatureFlags.is_enabled("ENABLE_DIAGNOSTICS_LEGACY"):
            nav_button_chiclet("Diagnostics", diagnostics_icon, "diagnostics")
        nav_button_chiclet("Impact", impact_icon, "impact_v2")


        # Client Report feature removed
        
        # Launch - Requires 'run_optimizer' (Creating campaigns)
        if has_permission_for_account(user, 'run_optimizer', st.session_state.get('permission_account_context')):
            nav_button_chiclet("Launch", rocket_icon, "creator")

        st.divider()
        
        # ADMIN SECTION
        if has_permission(user.role, 'manage_users'):
             st.markdown("##### ORGANIZATION")
             # Icons for new sections
             team_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>'
             billing_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><rect x="2" y="5" width="20" height="14" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line></svg>'
             
             nav_button_chiclet("Team", team_icon, "team_settings")
             # Billing is placeholder for now (Phase 3)
             # nav_button_chiclet("Billing", billing_icon, "billing")

        # PROFILE SECTION (Everyone)
        nav_button_chiclet("Profile", settings_icon, "profile")

        # =========================
        # SECONDARY / SYSTEM
        # =========================
        nav_button_chiclet("Data Setup", storage_icon, "data_hub")
        
        # SUPER ADMIN SECTION
        # Check against DEFAULT_ADMIN_EMAIL or a config list
        # We hardcode admin@saddl.io here as per plan for simplicity/security
        

        if user.email and user.email.lower().strip() == "admin@saddl.io":
            platform_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{nav_icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>'
            nav_button_chiclet("Platform Admin", platform_icon, "platform_admin")
            
        # Account Settings (Merged into Profile)
        nav_button_chiclet("Help", help_icon, "readme")
        
        # Show undo toast if available
        from ui.action_confirmation import show_undo_toast
        show_undo_toast()
        
    # Routing
    current = st.session_state.get('current_module', 'home')

    # Full-page loading layer to mask stale UI while the next page is rendering.
    nav_loading = bool(st.session_state.get('_nav_loading', False))
    loading_overlay = st.empty()
    if nav_loading:
        loading_overlay.markdown(
            """
            <style>
                @keyframes page-loader-shimmer {
                    0% { background-position: -220% 0; }
                    100% { background-position: 220% 0; }
                }
                @keyframes page-loader-pulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.22); transform: scale(1); }
                    50% { box-shadow: 0 0 0 10px rgba(56, 189, 248, 0.04); transform: scale(1.02); }
                }
                .page-loader-overlay {
                    position: fixed;
                    inset: 0;
                    z-index: 999998;
                    background:
                        radial-gradient(circle at 18% 12%, rgba(56, 189, 248, 0.08), transparent 36%),
                        radial-gradient(circle at 82% 88%, rgba(94, 234, 212, 0.04), transparent 42%),
                        #0a0f1e;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                [data-testid="stSidebar"] {
                    z-index: 1000000 !important;
                    position: relative !important;
                }
                .page-loader-card {
                    width: min(680px, 82vw);
                    border-radius: 16px;
                    border: 1px solid rgba(148, 163, 184, 0.16);
                    background: linear-gradient(140deg, rgba(15, 23, 42, 0.7), rgba(15, 23, 42, 0.52));
                    backdrop-filter: blur(10px);
                    box-shadow:
                        0 24px 64px rgba(2, 6, 23, 0.52),
                        inset 0 1px 0 rgba(255, 255, 255, 0.04),
                        0 0 0 1px rgba(56, 189, 248, 0.06);
                    padding: 20px 20px 18px 20px;
                }
                .page-loader-head {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-bottom: 14px;
                }
                .page-loader-spinner {
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    border: 2px solid rgba(100, 116, 139, 0.28);
                    border-top-color: rgba(56, 189, 248, 0.92);
                    border-right-color: rgba(56, 189, 248, 0.55);
                    animation: page-loader-spin 0.9s linear infinite;
                    box-shadow: 0 0 14px rgba(56, 189, 248, 0.14);
                }
                .page-loader-text {
                    color: rgba(203, 213, 225, 0.82);
                    font-size: 0.95rem;
                    font-weight: 400;
                    letter-spacing: 0.01em;
                }
                @keyframes page-loader-spin {
                    to { transform: rotate(360deg); }
                }
                .page-loader-line {
                    height: 10px;
                    border-radius: 8px;
                    margin: 8px 0;
                    background:
                        linear-gradient(
                            90deg,
                            rgba(30, 41, 59, 0.55) 0%,
                            rgba(100, 116, 139, 0.14) 40%,
                            rgba(148, 163, 184, 0.26) 50%,
                            rgba(100, 116, 139, 0.14) 60%,
                            rgba(30, 41, 59, 0.55) 100%
                        );
                    background-size: 220% 100%;
                    animation: page-loader-shimmer 1.5s ease-in-out infinite;
                }
                .page-loader-line.w-100 { width: 100%; }
                .page-loader-line.w-82 { width: 82%; }
                .page-loader-line.w-64 { width: 64%; }
            </style>
            <div class="page-loader-overlay">
                <div class="page-loader-card">
                    <div class="page-loader-head">
                        <span class="page-loader-spinner"></span>
                        <span class="page-loader-text">Preparing your data...</span>
                    </div>
                    <div class="page-loader-line w-100"></div>
                    <div class="page-loader-line w-82"></div>
                    <div class="page-loader-line w-64"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Check for pending actions confirmation dialog - REMOVED per user request
    # Actions are now saved explicitly via "Save Run" button in optimizer
    # from ui.action_confirmation import render_action_confirmation_modal
    # render_action_confirmation_modal()

    # Show test mode warning banner
    if st.session_state.get('test_mode', False):
        st.warning("⚠️ **TEST MODE ACTIVE** — All data is being saved to `ppc_test.db`. Switch off to use production database.")

    # Create main content container for proper clearing
    main_content = st.container()

    with main_content:
        if current == 'home':
            render_home()

        elif current == 'data_hub':
            import importlib
            import sys
            # Clear module cache to prevent KeyError
            if 'ui.data_hub' in sys.modules:
                importlib.reload(sys.modules['ui.data_hub'])
                from ui.data_hub import render_data_hub
            else:
                from ui.data_hub import render_data_hub
            render_data_hub()

        elif current == 'platform_admin':
            # Strictly verify access even if session state thinks we are here
            if user.email and user.email.lower().strip() == "admin@saddl.io":
                from features.platform_admin import render_platform_admin
                render_platform_admin()
            else:
                # Unauthorized access attempt or sticky session state - reset to home
                st.session_state['_nav_loading'] = True
                st.session_state['current_module'] = 'home'
                st.rerun()

        elif current == 'account_settings':
            # Route legacy calls to consolidated module
            from features.account_settings import run_account_settings
            run_account_settings()

        elif current == 'team_settings':
            try:
                from ui.auth.user_management import render_user_management
                render_user_management()
            except Exception as e:
                st.error(f"❌ Teams page error: {e}")
                st.exception(e)

        elif current == 'profile':
            from features.account_settings import run_account_settings
            run_account_settings()

        elif current == 'billing':
            st.info("Billing module coming in Phase 3.")

        elif current == 'readme':
            from ui.readme import render_readme
            render_readme()

        elif current == 'optimizer':
            from features.optimizer_v2.main import render_optimizer_v2
            render_optimizer_v2()

        elif current == 'simulator':
            from features.simulator import SimulatorModule
            SimulatorModule().run()

        elif current == 'diagnostics':
            run_diagnostics_hub()

        elif current == 'performance':
            run_performance_hub()

        elif current == 'creator':
            from features.creator import CreatorModule
            creator = CreatorModule()
            creator.run()

        elif current == 'assistant':
            try:
                from features.assistant import AssistantModule
                AssistantModule().render_interface()
            except Exception as e:
                st.error(f"Assistant module is unavailable in this deployment: {e}")
                st.info("Continuing without Assistant. Please check deployment dependencies/logs.")

        # ASIN/AI modules are now inside Optimizer, but we keep routing valid just in case
        elif current == 'asin_mapper':
            from features.asin_mapper import ASINMapperModule
            ASINMapperModule().run()

        elif current == 'debug_impact':
            from features.debug_ui import render_debug_metrics
            render_debug_metrics()

        elif current == 'ai_insights':
            from features.kw_cluster import AIInsightsModule
            AIInsightsModule().run()

        # Legacy impact_dashboard.py wiring removed - v2 is now primary
        elif current == 'impact_v2':
            from features.impact.main import render_impact_dashboard_v2
            render_impact_dashboard_v2()
        # Client Report feature removed

    # Render Floating Chat Bubble (unless already on assistant page)
    if current != 'assistant':
        try:
            from features.assistant import AssistantModule
            assistant = AssistantModule()
            assistant.render_floating_interface()
            assistant.render_interface()
        except Exception:
            # Non-fatal in environments where assistant dependencies are unavailable.
            pass

    if nav_loading:
        st.session_state['_nav_loading'] = False
        loading_overlay.empty()

if __name__ == "__main__":
    main()
