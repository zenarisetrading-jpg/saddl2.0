import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


def _to_datetime_series(values):
    try:
        return pd.to_datetime(values, errors="coerce")
    except Exception:
        return pd.Series(dtype="datetime64[ns]")


def _get_date_col(df: pd.DataFrame):
    for col in ["Date", "start_date", "Start Date", "date"]:
        if col in df.columns:
            return col
    return None


def _compute_spend_trend(df_stats: pd.DataFrame) -> str:
    if df_stats is None or df_stats.empty or "Spend" not in df_stats.columns:
        return "Unavailable"

    date_col = _get_date_col(df_stats)
    if not date_col:
        return "Unavailable"

    data = df_stats.copy()
    data[date_col] = _to_datetime_series(data[date_col])
    data = data.dropna(subset=[date_col])
    if data.empty:
        return "Unavailable"

    end_date = data[date_col].max()
    start_cutoff = end_date - timedelta(days=28)
    data = data[data[date_col] >= start_cutoff]
    if data.empty:
        return "Unavailable"

    data["week"] = data[date_col].dt.to_period("W").astype(str)
    week_spend = data.groupby("week", as_index=False)["Spend"].sum()

    if len(week_spend) < 2:
        return "Stable"

    first_week = float(week_spend.iloc[0]["Spend"])
    last_week = float(week_spend.iloc[-1]["Spend"])

    if first_week <= 0:
        return "Stable"

    delta_pct = ((last_week - first_week) / first_week) * 100
    if delta_pct >= 5:
        return f"Rising (+{delta_pct:.1f}% vs 4 weeks ago)"
    if delta_pct <= -5:
        return f"Declining ({delta_pct:.1f}% vs 4 weeks ago)"
    return f"Stable ({delta_pct:+.1f}% vs 4 weeks ago)"


def _extract_health_metrics(db, client_id: str):
    metrics = {
        "spend_trend": "Unavailable",
        "improved": None,
        "worsened": None,
        "cooldown_targets": 0,
        "cooldown_last_actioned": "n/a",
        "last_optimization": "Never",
        "save_status": "No saved runs",
    }

    try:
        df_stats = db.get_target_stats_df(client_id)
        metrics["spend_trend"] = _compute_spend_trend(df_stats)
    except Exception:
        pass

    recent_actions = []
    try:
        recent_actions = db.get_recent_actions(client_id, limit=50000)
    except Exception:
        recent_actions = []

    if recent_actions:
        actions_df = pd.DataFrame(recent_actions)
        if "action_date" in actions_df.columns:
            actions_df["action_date"] = _to_datetime_series(actions_df["action_date"])
            actions_df = actions_df.dropna(subset=["action_date"])

            if not actions_df.empty:
                last_opt = actions_df["action_date"].max()
                metrics["last_optimization"] = last_opt.strftime("%Y-%m-%d")
                metrics["save_status"] = "Saved"

                cooldown_cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
                cooldown_df = actions_df[
                    actions_df["action_date"] >= cooldown_cutoff
                ]

                key_cols = [c for c in ["campaign_name", "ad_group_name", "target_text"] if c in cooldown_df.columns]
                if key_cols:
                    metrics["cooldown_targets"] = int(cooldown_df[key_cols].drop_duplicates().shape[0])
                else:
                    metrics["cooldown_targets"] = int(len(cooldown_df))

                if not cooldown_df.empty:
                    metrics["cooldown_last_actioned"] = cooldown_df["action_date"].max().strftime("%Y-%m-%d")

    try:
        impact = db.get_impact_summary(client_id)
        if isinstance(impact, dict):
            if "winners" in impact and "losers" in impact:
                metrics["improved"] = int(impact.get("winners", 0))
                metrics["worsened"] = int(impact.get("losers", 0))
            elif "validated" in impact and isinstance(impact["validated"], dict):
                validated = impact["validated"]
                metrics["improved"] = int(validated.get("n_win", 0))
                metrics["worsened"] = int(validated.get("n_loss", 0))
    except Exception:
        pass

    return metrics


def render_v2_entry_screen():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Manrope:wght@400;500;700&display=swap');

        .v2-shell {
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 18px;
            padding: 24px;
            background:
              radial-gradient(circle at 12% 8%, rgba(20, 184, 166, 0.14), transparent 35%),
              radial-gradient(circle at 88% 4%, rgba(56, 189, 248, 0.12), transparent 38%),
              linear-gradient(160deg, rgba(15, 23, 42, 0.94), rgba(3, 7, 18, 0.96));
            box-shadow: 0 18px 40px rgba(2, 6, 23, 0.45);
            margin-bottom: 18px;
        }

        .v2-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.15rem;
            letter-spacing: 0.02em;
            color: #e2e8f0;
            margin-bottom: 14px;
            font-weight: 700;
        }

        .v2-line {
            font-family: 'Manrope', sans-serif;
            color: #cbd5e1;
            font-size: 0.98rem;
            margin: 8px 0;
        }

        .v2-kv {
            color: #f8fafc;
            font-weight: 700;
        }

        .v2-muted {
            color: #94a3b8;
            font-size: 0.85rem;
        }

        .v2-controls {
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 14px;
            padding: 18px;
            background: rgba(15, 23, 42, 0.55);
        }

        div[data-testid="stVerticalBlock"] > div:has(> .stDateInput),
        div[data-testid="stVerticalBlock"] > div:has(> .stRadio),
        div[data-testid="stVerticalBlock"] > div:has(> .stCheckbox) {
            font-family: 'Manrope', sans-serif;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    client_id = st.session_state.get("active_account_id")
    db = st.session_state.get("db_manager")

    if not client_id or not db:
        st.warning("Please select an active account from the sidebar.")
        return

    with st.spinner("Preparing pre-run intelligence brief..."):
        metrics = _extract_health_metrics(db, client_id)

    improved_text = "n/a" if metrics["improved"] is None else str(metrics["improved"])
    worsened_text = "n/a" if metrics["worsened"] is None else str(metrics["worsened"])

    st.markdown(
        f"""
        <div class="v2-shell">
            <div class="v2-title">Account Health (last 4 weeks)</div>
            <div class="v2-line">├── Spend trend: <span class="v2-kv">{metrics['spend_trend']}</span></div>
            <div class="v2-line">├── Decisions pending from last run: <span class="v2-kv">{improved_text} improved, {worsened_text} worsened</span></div>
            <div class="v2-line">├── Targets in cooldown: <span class="v2-kv">{metrics['cooldown_targets']}</span> <span class="v2-muted">(last actioned {metrics['cooldown_last_actioned']})</span></div>
            <div class="v2-line">└── Last optimization: <span class="v2-kv">{metrics['last_optimization']}</span> <span class="v2-muted">→ Save status: {metrics['save_status']}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "opt_start_date" not in st.session_state:
        st.session_state["opt_start_date"] = datetime.today().date() - timedelta(days=30)
    if "opt_end_date" not in st.session_state:
        st.session_state["opt_end_date"] = datetime.today().date()

    c1, c2 = st.columns([1.2, 1], gap="large")

    with c1:
        with st.container(border=True):
            st.markdown("**Analysis window**")
            d1, d2 = st.columns(2)
            with d1:
                st.date_input("Start", key="opt_start_date")
            with d2:
                st.date_input("End", key="opt_end_date")

    with c2:
        with st.container(border=True):
            st.markdown("**Strategy**")
            st.radio(
                "Risk profile",
                options=["Conservative", "Balanced", "Aggressive"],
                key="opt_risk_profile",
                horizontal=True,
                label_visibility="collapsed",
            )
            st.checkbox("Include simulation", key="opt_run_sim", value=False)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    if st.button("Start Optimization →", type="primary", width='stretch', key="start_v2_opt"):
        st.session_state["_nav_loading"] = True
        st.session_state["v2_opt_state"] = "running"
        st.rerun()
