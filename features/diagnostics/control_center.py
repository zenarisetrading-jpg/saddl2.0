"""Main entry point for the Diagnostics Control Center v2.1."""
import streamlit as st
import pandas as pd
from app_core.utils import IMPACT_WINDOWS
from features.impact.data.fetchers import fetch_impact_data

from features.diagnostics.styles import inject_diagnostics_css
from components.diagnostic_cards import (
    render_health_card,
    render_visual_proof,
    render_actions,
    render_asin_table
)
from utils.diagnostics import (
    compute_health_score,
    generate_primary_diagnosis,
    get_revenue_breakdown,
    get_bsr_trend,
    get_bsr_traffic_overlay,
    detect_cvr_divergence,
    get_optimization_performance,
    generate_multi_dimensional_actions,
    get_asin_action_table,
)


def render_control_center(client_id: str):
    """Render the main diagnostics page."""
    st.markdown('<div class="diag-shell">', unsafe_allow_html=True)
    inject_diagnostics_css()

    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown('<div class="diag-title-lg">Diagnostic Control Center</div>', unsafe_allow_html=True)
        st.markdown('<div class="diag-text-sm">Visual proof + multi-dimensional action planning</div>', unsafe_allow_html=True)
    with c2:
        if st.button("Refresh Analysis", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    impact_horizon_key = st.session_state.get("impact_horizon_v2", IMPACT_WINDOWS["default_horizon"])
    impact_days = IMPACT_WINDOWS["horizons"].get(
        impact_horizon_key, IMPACT_WINDOWS["horizons"][IMPACT_WINDOWS["default_horizon"]]
    )["days"]
    impact_validated_only = bool(st.session_state.get("validated_only_toggle_v2", True))
    st.caption(
        f"Impact basis aligned to Impact Dashboard: {impact_horizon_key} "
        f"({'validated only' if impact_validated_only else 'all actions'})"
    )

    with st.spinner("Analyzing account health..."):
        try:
            health = compute_health_score(client_id, days=30)
            diagnosis = generate_primary_diagnosis(health, days=30)
            revenue = get_revenue_breakdown(days=90, client_id=client_id)
            bsr = get_bsr_trend(days=90, client_id=client_id)
            traffic_bsr = get_bsr_traffic_overlay(days=90, client_id=client_id)
            cvr = detect_cvr_divergence(days=90, client_id=client_id)
            optimization = get_optimization_performance(days=30, client_id=client_id, validated_only=impact_validated_only)
            test_mode = st.session_state.get("test_mode", False)
            cache_version = "diag_" + str(st.session_state.get("data_upload_timestamp", "init"))
            impact_df, full_summary = fetch_impact_data(
                client_id=client_id,
                test_mode=test_mode,
                before_days=IMPACT_WINDOWS["before_window_days"],
                after_days=impact_days,
                cache_version=cache_version,
            )
            if not impact_df.empty and "action_date" in impact_df.columns:
                impact_df["action_date"] = pd.to_datetime(impact_df["action_date"], errors="coerce")
                latest_data_date = st.session_state.get("latest_data_date")
                if latest_data_date is None:
                    period_info = full_summary.get("period_info", {})
                    latest_data_date = period_info.get("after_end") or period_info.get("latest_date")
                if latest_data_date is not None:
                    latest_data_date = pd.to_datetime(latest_data_date)
                    impact_df["is_mature"] = impact_df["action_date"].le(latest_data_date - pd.Timedelta(days=impact_days + IMPACT_WINDOWS["maturity_buffer_days"]))
                else:
                    impact_df["is_mature"] = True
            if impact_df.empty:
                active_df = impact_df
            else:
                display_df = impact_df.copy()
                if impact_validated_only and "validation_status" in display_df.columns:
                    v_mask = display_df["validation_status"].astype(str).str.contains(
                        "✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume|Strict",
                        na=False,
                        regex=True,
                    )
                    display_df = display_df[v_mask].copy()
                if "is_mature" in display_df.columns:
                    mature_df = display_df[display_df["is_mature"] == True].copy()
                else:
                    mature_df = display_df.copy()
                before_spend = mature_df["before_spend"].fillna(0) if "before_spend" in mature_df.columns else pd.Series(0, index=mature_df.index)
                after_spend = mature_df["observed_after_spend"].fillna(0) if "observed_after_spend" in mature_df.columns else pd.Series(0, index=mature_df.index)
                spend_mask = (before_spend + after_spend) > 0
                active_df = mature_df[spend_mask].copy()
            impact_summary = full_summary.get("validated" if impact_validated_only else "all", {}) if isinstance(full_summary, dict) else {}
            actions = generate_multi_dimensional_actions(diagnosis=diagnosis, health=health, days=30, client_id=client_id)
            asin_actions = get_asin_action_table(days=30, client_id=client_id)

            render_health_card(health, diagnosis)
            render_visual_proof(
                revenue=revenue,
                bsr=bsr,
                traffic_bsr=traffic_bsr,
                cvr=cvr,
                optimization=optimization,
                impact_summary=impact_summary,
                impact_df=active_df,
            )
            go_optimizer = render_actions(actions)
            if go_optimizer:
                st.session_state["_nav_loading"] = True
                st.session_state["current_module"] = "optimizer"
                st.rerun()
            render_asin_table(asin_actions)

        except Exception as e:
            st.error(f"Error loading diagnostics: {str(e)}")
            st.exception(e)
            
    st.markdown('</div>', unsafe_allow_html=True)
