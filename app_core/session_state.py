"""
Centralized session state initialization.

Call init_session_state() once at app startup to ensure all known
session state keys have safe defaults, eliminating KeyError crashes.

RULE FOR MAINTAINERS
--------------------
Only add keys here if BOTH of the following are true:
  1. The key has a safe "empty" default (False, 0, "", [], {}, or None-for-dates)
  2. No code uses `if 'key' in st.session_state:` as a "has this been computed?"
     presence sentinel.

DO NOT add result/output keys (optimizer_results, latest_asin_analysis, etc.)
These are set only after an operation completes; pre-populating them with None
causes `if key in st.session_state:` guards to pass and `.get()` to crash.

DO NOT add auth/account identity keys (user, active_account_id, active_account,
active_account_name, permission_account_context). These use key-presence to
mean "an account has been selected" — see ui/account_manager.py.
"""
import streamlit as st


def init_session_state() -> None:
    """Initialize all known session state keys with safe defaults.

    Uses presence check so existing values are never overwritten.
    Safe to call on every Streamlit rerun.
    """
    defaults = {
        # --- Navigation ---
        "current_module": "home",
        "active_perf_tab": "Business Overview",
        "active_creator_tab": "Launch New Product",
        "active_opt_tab": "Overview",
        "active_neg_tab": "Keyword Negatives",
        "active_bid_tab": "Exact Keywords",
        "auth_view": "login",

        # --- Auth / Account (safe flags only) ---
        # user, current_user, active_account_id, active_account_name,
        # active_account, permission_account_context → NOT here (see module docstring)
        "amazon_connected": False,
        "amazon_client_id": "",
        "amazon_oauth_state": "",
        "client_id": "",
        "login_tracked": False,

        # --- Database / App Config ---
        "db_manager": None,  # safe: code checks `if st.session_state['db_manager']:` not `in`
        "test_mode": False,
        "theme_mode": "dark",
        "read_only_mode": False,

        # --- Data / Upload ---
        "unified_data": {
            "search_term_report": None,
            "advertised_product_report": None,
            "bulk_id_mapping": None,
            "category_mapping": None,
            "enriched_data": None,
            "upload_status": {
                "search_term_report": False,
                "advertised_product_report": False,
                "bulk_id_mapping": False,
                "category_mapping": False,
            },
            "upload_timestamps": {},
        },
        "data_upload_timestamp": None,  # date — consumers check `if x is not None:`
        "data_version": "v1",
        "last_stats_save": {},
        "latest_data_date": None,        # date — consumers check `if x is not None:`

        # --- Optimizer (config & flags only) ---
        # optimizer_results_refactored, optimizer_results, latest_optimizer_run,
        # pending_actions → NOT here; set only after optimizer runs.
        # optimizer_shared/__init__.py uses `if 'optimizer_results_refactored' in ss:`
        # as "has optimizer run?" — pre-populating with None causes crash.
        "run_optimizer_refactored": False,
        "optimizer_config": {},
        "optimizer_css_injected": False,
        "optimizer_actions_accepted": False,
        "opt_profile": "balanced",
        "opt_risk_profile": "Balanced",
        "opt_target_roas": 2.5,
        "opt_neg_clicks_threshold": 10,
        "opt_min_clicks_exact": 5,
        "opt_min_clicks_pt": 5,
        "opt_min_clicks_broad": 8,
        "opt_min_clicks_auto": 8,
        "opt_alpha_exact": 25,
        "opt_alpha_broad": 20,
        "opt_max_bid_change": 25,
        "opt_harvest_roas_mult": 85,
        "opt_test_mode": False,
        "opt_show_ids": False,
        # opt_start_date, opt_end_date, opt_date_start, opt_date_end → NOT here.
        # landing.py uses `if key not in st.session_state:` to compute date
        # defaults from the uploaded data. Pre-populating with None skips that
        # branch and leaves None where a real date is required.
        "consolidation_negatives": [],
        "trigger_save": False,

        # --- Optimizer V2 (config & flags only) ---
        # v2_opt_results → NOT here; set only after optimizer V2 runs.
        "v2_opt_state": "entry",
        "v21_commerce_fetch_ok": False,
        "v21_commerce_rows": 0,
        "v21_spapi_missing": False,

        # --- Performance / Reporting ---
        "target_roas": 3.0,
        "biz_overview_window": "30D",
        "ppc_window_days": 30,
        "ppc_match_filter": "All",
        "date_range": "",
        "exec_dash_date_range": "Last 30 Days",
        "report_config": {},
        "report_card_ai_summary": "",
        "show_client_report": False,
        "show_share_result": False,
        "_cockpit_data_source": "",

        # --- Impact Dashboard ---
        "_impact_metrics": {},
        "validated_only_toggle": True,
        "validated_only_toggle_v2": True,
        # impact_horizon_v2 → NOT here; computed result

        # --- ASIN / Cluster / AI (safe containers only) ---
        # latest_asin_analysis, harvest_payload → NOT here; set after analysis runs.
        # assistant.py uses `if 'latest_asin_analysis' in ss:` as "has analysis run?"
        "latest_ai_insights": {},          # safe: consumers do .get() on dict, not None
        "asin_mapper_integration_stats": {},

        # --- Chat / Assistant ---
        "messages": [],

        # --- Onboarding ---
        "show_onboarding": False,
        "onboarding_step": 1,
        "onboarding_completed": False,

        # --- UI Flags ---
        "show_account_form": False,
        "reassign_preview_active": False,

        # --- Action Confirmation / Navigation Guards ---
        "_show_action_confirmation": False,
        "_pending_navigation_target": None,  # None = no pending nav
        "_last_saved_batch_id": None,
        "_last_saved_client_id": None,
        "_undo_window_start": None,

        # --- Sidebar / Layout ---
        "_sidebar_state": "expanded",
        "sidebar_state": "expanded",
        "_main_menu_visibility": "hidden",
    }

    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
