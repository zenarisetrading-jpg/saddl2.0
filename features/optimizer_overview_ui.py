import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from features.optimizer_results_adapter import adapt_run_outputs
from features.optimizer_run_summary import RunSummaryBuilder
from utils.formatters import format_currency, get_account_currency

def render_overview_tab(raw_results: dict):
    """
    Main entry point for the Optimizer Overview Tab.
    Orchestrates the Adapter -> Builder -> UI pipeline.
    """
    # 1. Pipeline Execution
    try:
        # Adapter
        run_outputs = adapt_run_outputs(raw_results)
        
        # Builder
        builder = RunSummaryBuilder(run_outputs)
        summary = builder.build()
        
    except Exception as e:
        st.error(f"Error generating overview: {str(e)}")
        # Fallback empty state could go here
        return

    # 2. UI Rendering
    _render_header(summary)
    _render_kpi_cards(summary)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        _render_efficiency_chart(summary)
    with col2:
        _render_top_opportunities(summary)
        
    # Link footer handled by parent tab structure usually, but we can add shortcuts if needed

def _render_header(summary: dict):
    """Render run metadata and status."""
    meta = summary.get("metadata", {})
    ts = meta.get("timestamp")
    
    if isinstance(ts, datetime):
        time_str = ts.strftime("%b %d, %I:%M %p")
    else:
        time_str = "Just now"
        
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
            <span style="color: #8F8CA3; font-size: 0.9rem;">Last Run:</span>
            <span style="color: #F5F5F7; font-weight: 500; margin-left: 8px;">{time_str}</span>
        </div>
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); 
                    padding: 4px 12px; border-radius: 20px; color: #10B981; font-size: 0.85rem; font-weight: 600;">
            Optimization Complete
        </div>
    </div>
    """, unsafe_allow_html=True)

def _render_kpi_cards(summary: dict):
    """Render the 5 key metric cards."""
    
    currency = get_account_currency()
    
    # Extract Metrics
    waste = summary.get("waste_prevented")
    eff_gain = summary.get("efficiency_gain")
    bid_stats = summary.get("bid_stats", {})
    new_targets = summary.get("new_targets", 0)
    negatives = summary.get("negatives", 0)
    
    # Format strings
    waste_str = format_currency(waste, currency) if waste is not None else "—"
    eff_str = f"{eff_gain:.1%}" if eff_gain is not None else "—"
    
    # Bid formatting
    total_bids = bid_stats.get("total_actions", 0)
    bid_sub = f"{bid_stats.get('increases',0)} inc / {bid_stats.get('decreases',0)} dec"
    
    # CSS for cards
    card_style = """
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 20px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    backdrop-filter: blur(10px);
    """
    
    label_style = "color: #8F8CA3; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;"
    value_style = "color: #F5F5F7; font-size: 1.6rem; font-weight: 700;"
    sub_style = "color: #64748B; font-size: 0.8rem; margin-top: 4px;"
    
    cols = st.columns(5)
    
    # 1. Waste Prevented
    with cols[0]:
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{label_style}">Waste Prevented</div>
            <div style="{value_style}">{waste_str}</div>
            <div style="{sub_style}"><span style="color: #10B981;">Saved</span> from bleeders</div>
        </div>
        """, unsafe_allow_html=True)
        
    # 2. Efficiency Gain
    with cols[1]:
        color = "#10B981" if eff_gain and eff_gain > 0 else "#F5F5F7"
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{label_style}">Efficiency Gain</div>
            <div style="{value_style}; color: {color};">{eff_str}</div>
            <div style="{sub_style}">Projected ACOS red.</div>
        </div>
        """, unsafe_allow_html=True)
        
    # 3. Bid Adjustments
    with cols[2]:
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{label_style}">Bid Actions</div>
            <div style="{value_style}">{total_bids}</div>
            <div style="{sub_style}">{bid_sub}</div>
        </div>
        """, unsafe_allow_html=True)
        
    # 4. New Targets
    with cols[3]:
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{label_style}">New Targets</div>
            <div style="{value_style}">{new_targets}</div>
            <div style="{sub_style}">Harvest candidates</div>
        </div>
        """, unsafe_allow_html=True)
        
    # 5. Negatives
    with cols[4]:
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{label_style}">Negatives</div>
            <div style="{value_style}">{negatives}</div>
            <div style="{sub_style}">Blocked terms</div>
        </div>
        """, unsafe_allow_html=True)

def _render_efficiency_chart(summary: dict):
    """Render the Spend Contribution Stacked Bar."""
    st.markdown("### Efficiency Contribution")
    st.caption("How total spend (14d) is being reallocated by these actions")
    
    data = summary.get("contribution_chart", {})
    if not data:
        st.info("No spend data available for chart.")
        return
        
    # Data prep
    labels = ["Bid Up", "Unchanged", "Bid Down", "Negatives"]
    colors = ["#10B981", "#334155", "#F59E0B", "#EF4444"] # Green, Slate, Amber, Red
    
    # Ensure all keys exist
    values = []
    # Explicit mapping to ensure color consistency
    key_map = {
        "Bid Up": data.get("Bid Up", 0),
        "Unchanged": data.get("Unchanged", 0),
        "Bid Down": data.get("Bid Down", 0),
        "Negatives": data.get("Negatives", 0)
    }
    
    # Calculate Unchanged if not explicitly passed (since builder might omit it)
    total_alloc = sum(data.values())
    # If builder returns un-normalized or partial, we normalize to 100% implicitly by graph
    # But builder should handle normalization.
    # Let's rely on keys present.
    
    # Create single stacked bar
    fig = go.Figure()
    
    for label, color in zip(labels, colors):
        val = key_map.get(label, 0) * 100 # Convert to %
        if val > 0:
            fig.add_trace(go.Bar(
                name=label,
                y=["Spend"],
                x=[val],
                orientation='h',
                marker=dict(color=color)
            ))
            
    fig.update_layout(
        barmode='stack',
        height=120,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, showticklabels=True, range=[0, 100], ticksuffix="%"),
        yaxis=dict(showgrid=False, showticklabels=False)
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def _render_top_opportunities(summary: dict):
    """Render the Top Opportunities table."""
    st.markdown("### Top Opportunities")
    st.caption("Highest impact bid increases based on historical sales volume")
    
    ops = summary.get("top_opportunities", [])
    
    if not ops:
        st.info("No high-impact opportunities identified in this run.")
        return
        
    # Convert to DF for clean display
    display_data = []
    currency = get_account_currency()
    
    for op in ops:
        target_raw = op["target_id"].split("|")[-1] # Extract term from composite key
        display_data.append({
            "Target": target_raw,
            "Sales (14d)": format_currency(op["sales_14d"], currency),
            "Bid Change": f"{op['old_bid']:.2f} → {op['new_bid']:.2f}",
            "Est. Uplift": format_currency(op["uplift"], currency)
        })
        
    df_disp = pd.DataFrame(display_data)
    
    # Use standard dataframe or custom HTML table? Standard is safer for now.
    st.dataframe(
        df_disp,
        column_config={
            "Target": st.column_config.TextColumn("Target", width="medium"),
            "Sales (14d)": st.column_config.TextColumn("Sales Vol"),
            "Est. Uplift": st.column_config.TextColumn("Proj. Uplift"),
        },
        use_container_width=True,
        hide_index=True
    )
