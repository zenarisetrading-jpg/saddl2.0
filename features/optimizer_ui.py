
import streamlit as st
import pandas as pd
from datetime import timedelta
from utils.formatters import format_currency

def render_optimizer_control_panel(df, min_date, max_date, currency_symbol="$"):
    """
    Renders the complete Optimizer Control Panel.
    Uses CSS :has() selector to target the Streamlit Column container for the glassmorphic background.
    """
    # 1. Scope-Targeted CSS
    st.markdown("""
    <style>
    /* 
       TARGET THE COLUMN CONTAINER DIRECTLY 
       Using :has(#opt-panel-marker) ensures we only style THIS specific column 
       and wrap ALL widgets inside it (Dates, Metrics, Mode, Button).
    */
    div[data-testid="stVerticalBlock"]:has(div#opt-panel-marker) {
        background: radial-gradient(120% 120% at 50% 10%, rgba(255, 255, 255, 0.05) 0%, rgba(15, 23, 42, 0.7) 100%);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 1px solid rgba(255, 255, 255, 0.15); /* Highlight */
        border-bottom: 1px solid rgba(0, 0, 0, 0.4);      /* Shadow */
        border-radius: 20px;
        padding: 30px !important;
        gap: 10px !important; /* Adjust internal spacing */
        box-shadow: 
            0 20px 40px -10px rgba(0, 0, 0, 0.6),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }
    
    /* Metrics Row Flexbox */
    .metric-flex {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 25px;
        margin: 20px 0;
        padding: 20px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .metric-item { 
        text-align: center; 
        padding: 0 15px; 
    }
    .metric-val { 
        font-family: 'Inter', sans-serif; 
        font-size: 1.6rem; 
        font-weight: 700; 
        color: #F1F5F9; 
        text-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    .metric-lbl { 
        font-size: 0.75rem; 
        color: #94A3B8; 
        text-transform: uppercase; 
        letter-spacing: 1.2px; 
        margin-top: 6px; 
        font-weight: 600;
    }
    
    .metric-divider { 
        width: 1px; 
        background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.15), transparent); 
        height: 45px; 
    }
    
    /* Centered Radio Group */
    div[data-testid="stVerticalBlock"]:has(div#opt-panel-marker) div.stRadio > div[role="radiogroup"] {
        justify-content: center;
        width: 100%; /* Full width to allow centering flexibility */
        background: transparent;
        border: none;
        box-shadow: none;
        gap: 15px; /* Add spacing between options */
    }
    
    div[data-testid="stVerticalBlock"]:has(div#opt-panel-marker) div.stRadio label {
        padding: 10px 24px !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        border: 1px solid transparent;
        transition: all 0.2s ease;
    }
    
    div[data-testid="stVerticalBlock"]:has(div#opt-panel-marker) div.stRadio label:hover {
        background: rgba(255, 255, 255, 0.05);
        color: #E2E8F0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 2. State Management
    default_end = max_date.date() + timedelta(days=6)
    default_start = max(min_date, max_date - timedelta(days=30)).date()
    
    if "opt_date_start" not in st.session_state:
        st.session_state["opt_date_start"] = default_start
    if "opt_date_end" not in st.session_state:
        st.session_state["opt_date_end"] = default_end
        
    s_min, s_max = min_date.date(), max_date.date() + timedelta(days=6)
    if st.session_state["opt_date_start"] < s_min: st.session_state["opt_date_start"] = s_min
    if st.session_state["opt_date_end"] > s_max: st.session_state["opt_date_end"] = s_max

    # 3. Layout Rendering
    _, col_center, _ = st.columns([1, 6, 1])
    
    with col_center:
        # MARKER for CSS targeting (Invisible)
        st.markdown('<div id="opt-panel-marker"></div>', unsafe_allow_html=True)
        
        # Header (Standard Markdown now, pure widget flow)
        st.markdown('<h2 style="color: #F8FAFC; font-size: 1.4rem; font-weight: 600; text-align: center; margin-bottom: 25px;">Optimization Control Panel</h2>', unsafe_allow_html=True)
        
        # Date Pickers
        d1, d2 = st.columns(2)
        with d1:
            start_date = st.date_input("Start Date", value=st.session_state["opt_date_start"], min_value=s_min, max_value=s_max, key="p_start")
        with d2:
            end_date = st.date_input("End Date", value=st.session_state["opt_date_end"], min_value=s_min, max_value=s_max, key="p_end")
            
        st.session_state["opt_date_start"] = start_date
        st.session_state["opt_date_end"] = end_date
        
        # Metrics Logic
        date_col = next((c for c in ["Date", "Start Date", "date"] if c in df.columns), None)
        filtered_df = df
        if date_col:
            if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            mask = (df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)
            filtered_df = df[mask]
            
        rows = len(filtered_df)
        spend = filtered_df["Spend"].sum() if "Spend" in filtered_df.columns else 0
        sales = filtered_df["Sales"].sum() if "Sales" in filtered_df.columns else 0
        roas = sales / spend if spend > 0 else 0
        acos = (spend / sales * 100) if sales > 0 else 0
        
        # Metrics Visual
        st.markdown(f"""
        <div class="metric-flex">
            <div class="metric-item">
                <div class="metric-val">{rows:,}</div>
                <div class="metric-lbl">Rows</div>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
                <div class="metric-val">{format_currency(spend, currency_symbol)}</div>
                <div class="metric-lbl">Spend</div>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
                <div class="metric-val">{roas:.2f}x</div>
                <div class="metric-lbl">ROAS</div>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
                <div class="metric-val">{acos:.1f}%</div>
                <div class="metric-lbl">ACoS</div>
            </div>
        </div>
        
        <div style="text-align: center; margin-bottom: 20px; font-weight: 500; color: #E2E8F0;">Optimization Mode</div>
        """, unsafe_allow_html=True)
        
        # Mode
        mode = st.radio(
            "Select Optimization Mode",
            ["Conservative", "Balanced", "Aggressive"],
            index=1,
            label_visibility="collapsed",
            horizontal=True,
            key="opt_mode_main"
        )
        
        # Spacer
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        
        # Run Button
        run_clicked = st.button("🚀 Run Analysis & Optimize", type="primary", use_container_width=True)
        
    return {"run": run_clicked, "mode": mode, "start_date": start_date, "end_date": end_date}
