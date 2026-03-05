"""
Optimizer Module (Refactored)
Main orchestrator for bid optimization, harvest, and negative keyword logic.
"""

import pandas as pd
import numpy as np
import streamlit as st
from features._base import BaseFeature
from utils.matchers import ExactMatcher
from features.optimizer_shared.core import (
    prepare_data,
    calculate_account_benchmarks, 
    calculate_account_health,
    DEFAULT_CONFIG,
    CVR_CONFIG,
    OPTIMIZATION_PROFILES
)
from features.optimizer_shared.strategies.harvest import identify_harvest_candidates
from features.optimizer_shared.strategies.negatives import identify_negative_candidates
from features.optimizer_shared.strategies.bids import calculate_bid_optimizations
from features.optimizer_shared.simulation import run_simulation
from features.optimizer_shared.ui.heatmap import create_heatmap
from features.optimizer_shared.logging import log_optimization_events
from features.optimizer_shared.ppc_cascade import compute_ppc_cascade
from features.optimizer_shared.campaign_recommendations import generate_campaign_recommendations
from dev_resources.tests.bulk_validation_spec import OptimizationRecommendation

# UI Imports
from features.optimizer_shared.ui.components import inject_optimizer_css
from features.optimizer_shared.ui.landing import render_landing_page
from features.optimizer_shared.ui.results import render_results_dashboard

class OptimizerModule(BaseFeature):
    def __init__(self):
        super().__init__()
        # Initialize session state for config if not present
        if "opt_profile" not in st.session_state:
            st.session_state["opt_profile"] = "balanced"  # Default profile
        if "opt_harvest_roas_mult" not in st.session_state:
            st.session_state["opt_harvest_roas_mult"] = 85  # Default 85% (Balanced)
        if "opt_alpha_exact" not in st.session_state:
            st.session_state["opt_alpha_exact"] = 25  # 25% step
        if "opt_alpha_broad" not in st.session_state:
            st.session_state["opt_alpha_broad"] = 20  # 20% step
        if "opt_max_bid_change" not in st.session_state:
            st.session_state["opt_max_bid_change"] = 25  # 25% cap
        if "opt_target_roas" not in st.session_state:
            st.session_state["opt_target_roas"] = 2.5
        if "opt_neg_clicks_threshold" not in st.session_state:
            st.session_state["opt_neg_clicks_threshold"] = 10
        if "opt_min_clicks_exact" not in st.session_state:
            st.session_state["opt_min_clicks_exact"] = 5
        if "opt_min_clicks_pt" not in st.session_state:
            st.session_state["opt_min_clicks_pt"] = 5
        if "opt_min_clicks_broad" not in st.session_state:
            st.session_state["opt_min_clicks_broad"] = 8
        if "opt_min_clicks_auto" not in st.session_state:
            st.session_state["opt_min_clicks_auto"] = 8
        if "opt_test_mode" not in st.session_state:
            st.session_state["opt_test_mode"] = False
            
        self.config = DEFAULT_CONFIG.copy()
        # Ensure test mode is respected
        self.config["TEST_MODE"] = st.session_state.get("opt_test_mode", False)
        
        self.matcher = None
        self.results = {}

    def render_ui(self):
        """
        Main UI rendering method. Switches between Landing Page and Results Dashboard.
        Uses pure CSS/HTML injection for styling to preserve logic isolation.
        """
        # 1. Inject Global CSS for the Redesign (CACHED to prevent re-injection)
        if "optimizer_css_injected" not in st.session_state:
            inject_optimizer_css()
            st.session_state["optimizer_css_injected"] = True
        
        # 2. Sync Config from Session State (needed for calculation)
        self._sync_config_from_state()

        # 3. Check Data Availability (try database first, then session upload)
        from app_core.data_hub import DataHub
        hub = DataHub()

        # If no data in session, try loading from database
        if not hub.is_loaded("search_term_report"):
            account_id = st.session_state.get('active_account_id')
            if account_id:
                loaded = hub.load_from_database(account_id)

            # Check again after database load attempt
            if not hub.is_loaded("search_term_report"):
                st.warning("⚠️ No data found for this account.")
                st.info("Go to **Data Hub** → Upload files or sync data from Amazon")
                return

        # 4. Handle Optimization Run Logic (using separate key to avoid conflicts with legacy UI)
        if st.session_state.get("run_optimizer_refactored"):
            with st.container():
                # Load Data from DATABASE (not CSV) and apply date filtering
                from app_core.db_manager import get_db_manager
                import pandas as pd
                from datetime import timedelta
                from features.optimizer_shared.data_access import fetch_target_stats_cached

                client_id = st.session_state.get('active_account_id')
                test_mode = st.session_state.get('test_mode', False)

                # Engine uses weekly target_stats — thresholds (MIN_CLICKS, HARVEST_ORDERS)
                # are calibrated to weekly aggregated rows, not daily rows.
                if client_id:
                    df = fetch_target_stats_cached(client_id, test_mode)

                    # Apply date filtering based on session state
                    if not df.empty and 'Date' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

                        # Get selected date range from session state
                        start_date = st.session_state.get("opt_start_date")
                        end_date = st.session_state.get("opt_end_date")

                        if start_date and end_date:
                            # Filter to selected date range
                            mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
                            df = df[mask].copy()
                else:
                    # Fallback to uploaded data if no database
                    enriched_data = hub.get_enriched_data()
                    if enriched_data is not None and not enriched_data.empty:
                        df = enriched_data
                    else:
                        df = hub.get_data("search_term_report")

                # Run Analysis
                self._run_analysis(df)

                # Reset Flag
                st.session_state["run_optimizer_refactored"] = False

                # Force Rerun to update view
                st.rerun()

        # 5. Render View
        if 'optimizer_results_refactored' in st.session_state:
            # Show Post-Optimization Dashboard
            self.results = st.session_state['optimizer_results_refactored']
            render_results_dashboard(self.results)
        else:
            # Show Landing Page
            render_landing_page(self.config)

    def _sync_config_from_state(self):
        """Syncs session state values to self.config before analysis."""
        # 1. Apply Profile Params first (Core Logic)
        profile_name = st.session_state.get("opt_profile", "balanced")
        profile_params = OPTIMIZATION_PROFILES.get(profile_name, OPTIMIZATION_PROFILES["balanced"])["params"]
        self.config.update(profile_params)
        
        # 2. Apply explicit user overrides where applicable (e.g. Target ROAS)
        self.config["TARGET_ROAS"] = st.session_state["opt_target_roas"]
        
        # 3. Legacy/Granular overrides (If we want UI sliders to still work, we map them here)
        # However, Profile usually takes precedence for Logic Params.
        # We will let Profile drive Logic Params (Multipliers) and Session State drive Thresholds (Clicks).
        
        # self.config["HARVEST_ROAS_MULT"] is now set by profile!
        # Unless we want to allow slider override? 
        # For now, let's strictly follow the "Drive Mode" philosophy: Profile dictating the engine map.
        
        self.config["NEGATIVE_CLICKS_THRESHOLD"] = st.session_state["opt_neg_clicks_threshold"]
        self.config["ALPHA_EXACT"] = st.session_state["opt_alpha_exact"] / 100.0
        self.config["ALPHA_BROAD"] = st.session_state["opt_alpha_broad"] / 100.0
        self.config["MAX_BID_CHANGE"] = st.session_state["opt_max_bid_change"] / 100.0
        self.config["TARGET_ROAS"] = st.session_state["opt_target_roas"]
        self.config["NEGATIVE_CLICKS_THRESHOLD"] = st.session_state["opt_neg_clicks_threshold"]
        self.config["MIN_CLICKS_EXACT"] = st.session_state["opt_min_clicks_exact"]
        self.config["MIN_CLICKS_PT"] = st.session_state["opt_min_clicks_pt"]
        self.config["MIN_CLICKS_BROAD"] = st.session_state["opt_min_clicks_broad"]
        self.config["MIN_CLICKS_AUTO"] = st.session_state["opt_min_clicks_auto"]

    def _calculate_account_health(self, df: pd.DataFrame, r: dict) -> dict:
        """Calculate account health diagnostics for dashboard display."""
        return calculate_account_health(df)

    def _run_analysis(self, df):
        """
        Two-phase analysis:
          Phase 1 — Full dataset: cascade + Tier 1 campaign recommendations
                    (always from complete data so the panel shows all campaigns)
          Phase 2 — Bid engine: runs on filtered dataset if user has applied
                    Tier 1 exclusions, so account averages / quadrant thresholds
                    recalculate correctly for the remaining campaigns.
        """
        target_roas_val = self.config.get("TARGET_ROAS", 2.5)

        # ── Phase 1: full-dataset enrichment ─────────────────────────────────
        full_df, date_info = prepare_data(df, self.config)

        total_spend_full = full_df["Spend"].sum() if "Spend" in full_df.columns else 0
        total_sales_full = full_df["Sales"].sum() if "Sales" in full_df.columns else 0
        acct_metrics_full = {
            "roas": total_sales_full / total_spend_full if total_spend_full > 0 else 0,
            "acos": (total_spend_full / total_sales_full * 100) if total_sales_full > 0 else 100,
        }
        full_df_cascade = compute_ppc_cascade(
            df=full_df,
            target_roas=target_roas_val,
            account_metrics_current=acct_metrics_full,
            account_metrics_prior=None,
        )
        # Tier 1 recs always derive from full dataset
        campaign_recs = generate_campaign_recommendations(full_df_cascade, target_roas_val, self.config)

        # ── Phase 2: bid engine on (possibly filtered) dataset ────────────────
        accepted = st.session_state.get("tier1_accepted_campaigns", [])
        if accepted:
            # Filter full_df (already prepare_data-processed) and re-run cascade
            # so account averages and thresholds reflect only remaining campaigns.
            df_filtered = full_df[~full_df["Campaign Name"].isin(accepted)].copy()
            total_spend_f = df_filtered["Spend"].sum() if "Spend" in df_filtered.columns else 0
            total_sales_f = df_filtered["Sales"].sum() if "Sales" in df_filtered.columns else 0
            acct_metrics_f = {
                "roas": total_sales_f / total_spend_f if total_spend_f > 0 else 0,
                "acos": (total_spend_f / total_sales_f * 100) if total_sales_f > 0 else 100,
            }
            df_engine = compute_ppc_cascade(
                df=df_filtered,
                target_roas=target_roas_val,
                account_metrics_current=acct_metrics_f,
                account_metrics_prior=None,
            )
        else:
            df_engine = full_df_cascade

        benchmarks     = calculate_account_benchmarks(df_engine, self.config)
        universal_median = benchmarks.get('universal_median_roas', target_roas_val)

        matcher   = ExactMatcher(df_engine)
        harvest   = identify_harvest_candidates(df_engine, self.config, matcher, benchmarks)
        neg_kw, neg_pt, your_products = identify_negative_candidates(df_engine, self.config, harvest, benchmarks)

        neg_set   = set(zip(neg_kw["Campaign Name"], neg_kw["Ad Group Name"], neg_kw["Term"].str.lower()))
        data_days = date_info.get("days", 7) if date_info else 7
        client_id = st.session_state.get("active_account_id")

        bids_ex, bids_pt, bids_agg, bids_auto = calculate_bid_optimizations(
            df_engine,
            self.config,
            set(harvest["Customer Search Term"].str.lower()),
            neg_set,
            universal_median,
            data_days=data_days,
            client_id=client_id,
        )

        heatmap = create_heatmap(
            df_engine, self.config, harvest, neg_kw, neg_pt,
            pd.concat([bids_ex, bids_pt]), pd.concat([bids_agg, bids_auto]),
        )

        self.results = {
            "df": df_engine, "date_info": date_info,
            "harvest": harvest, "neg_kw": neg_kw, "neg_pt": neg_pt,
            "your_products_review": your_products,
            "bids_exact": bids_ex, "bids_pt": bids_pt, "bids_agg": bids_agg, "bids_auto": bids_auto,
            "direct_bids": pd.concat([bids_ex, bids_pt]),
            "agg_bids": pd.concat([bids_agg, bids_auto]),
            "heatmap": heatmap,
            "campaign_recs": campaign_recs,
            "simulation": run_simulation(
                df_engine, pd.concat([bids_ex, bids_pt]),
                pd.concat([bids_agg, bids_auto]), harvest, self.config, date_info,
            ),
        }
        st.session_state['optimizer_results_refactored'] = self.results

    # Required BaseFeature Implementations
    def validate_data(self, data): 
        """Validates input data (Placeholder)."""
        return True, ""
        
    def analyze(self, data): 
        """Public analysis entry point."""
        self._run_analysis(data)
        return self.results

    def display_results(self, results):
        """Legacy display entry point."""
        self.results = results
        self.render_ui() # Redirect to new UI

    # Legacy helper methods (kept for safety/compatibility if called externally)
    def _display_negatives(self, neg_kw, neg_pt):
        from features.optimizer_shared.ui.tabs.negatives import render_negatives_tab
        render_negatives_tab(neg_kw, neg_pt)

    def _display_bids(self, bids_exact=None, bids_pt=None, bids_agg=None, bids_auto=None):
        from features.optimizer_shared.ui.tabs.bids import render_bids_tab
        render_bids_tab(bids_exact, bids_pt, bids_agg, bids_auto)

    def _display_harvest(self, harvest_df):
        from features.optimizer_shared.ui.tabs.harvest import render_harvest_tab
        render_harvest_tab(harvest_df)

    def _display_heatmap(self, heatmap_df):
        from features.optimizer_shared.ui.tabs.audit import render_audit_tab
        render_audit_tab(heatmap_df)

    def _display_downloads(self, results):
        from features.optimizer_shared.ui.tabs.downloads import render_downloads_tab
        render_downloads_tab(results)
