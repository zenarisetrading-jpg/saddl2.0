"""
Waterfall Charts - ROAS waterfall and attribution charts.
Aligned with legacy impact_dashboard.py visuals.

v3.3 Integration: Uses roas_waterfall_v33 for proper counterfactual attribution.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, Optional

from features.impact.styles.css import BRAND_COLORS, get_chart_styles
from app_core.roas_waterfall_v33 import calculate_roas_waterfall_v33


def create_roas_waterfall_figure(
    summary: Dict[str, Any],
    currency: str = "$",
    height: int = 380
) -> go.Figure:
    """
    Create a ROAS waterfall chart figure.

    This is a factory function that returns a Plotly figure,
    used by client report generation.

    Args:
        summary: Summary dict with by_action_type breakdown
        currency: Currency symbol
        height: Chart height in pixels

    Returns:
        Plotly Figure object
    """
    by_type = summary.get('by_action_type', {})

    if not by_type:
        # Return empty figure
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig

    # Map raw types to display names
    display_names = {
        'BID_CHANGE': 'Bid Optim.',
        'NEGATIVE': 'Cost Saved',
        'HARVEST': 'Harvest Gains',
        'BID_ADJUSTMENT': 'Bid Optim.'
    }

    # Aggregate data
    agg_data = {}
    for t, data in by_type.items():
        name = display_names.get(t, t.replace('_', ' ').title())
        agg_data[name] = agg_data.get(name, 0) + data.get('net_sales', 0)

    # Sort
    sorted_data = sorted(agg_data.items(), key=lambda x: x[1], reverse=True)
    names = [x[0] for x in sorted_data]
    impacts = [x[1] for x in sorted_data]

    # Create waterfall
    fig = go.Figure(go.Waterfall(
        name="Impact",
        orientation="v",
        measure=["relative"] * len(impacts) + ["total"],
        x=names + ['Total'],
        y=impacts + [sum(impacts)],
        connector={"line": {"color": "rgba(148, 163, 184, 0.2)"}},
        decreasing={"marker": {"color": BRAND_COLORS['slate_light']}},
        increasing={"marker": {"color": BRAND_COLORS['purple']}},
        totals={"marker": {"color": BRAND_COLORS['cyan']}},
        textposition="outside",
        textfont=dict(size=14, color="#e2e8f0"),
        text=[f"{currency}{v:+,.0f}" for v in impacts] + [f"{currency}{sum(impacts):+,.0f}"]
    ))

    fig.update_layout(
        showlegend=False,
        height=height,
        margin=dict(t=60, b=40, l=30, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            tickformat=',.0f',
            tickfont=dict(color='#94a3b8', size=12)
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#cbd5e1', size=12)
        )
    )

    return fig


def render_roas_attribution_bar(
    summary: Dict[str, Any],
    impact_df: pd.DataFrame,
    currency: str,
    canonical_metrics: Optional[Any] = None,
    decision_impact_override: Optional[float] = None,
    timeline: Optional[Dict[str, Any]] = None
):
    """
    Render ROAS attribution waterfall chart - matches legacy _render_roas_attribution_bar.
    
    Features:
    - Baseline → Combined Forces → Decisions → Actual waterfall
    - VALUE CREATED box
    - Full Breakdown expander with Market/Structural analysis

    Args:
        summary: Summary dict from backend
        impact_df: Impact DataFrame
        currency: Currency symbol
        canonical_metrics: ImpactMetrics object
    """
    # Chart icon (cyan)
    chart_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); 
                border: 1px solid rgba(148, 163, 184, 0.15); 
                border-left: 3px solid #06B6D4;
                border-radius: 12px; padding: 16px; margin-bottom: 16px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
        <div style="display: flex; align-items: center; gap: 12px;">
            {chart_icon}
            <span style="font-weight: 700; font-size: 1.1rem; color: #F8FAFC; letter-spacing: 0.02em;">ROAS Attribution</span>
        </div>
        <div style="color: #64748B; font-size: 0.85rem; margin-top: 8px; margin-left: 32px;">
            Waterfall analysis of performance drivers
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if impact_df.empty:
        st.info("No data for attribution chart")
        return

    # =========================================================
    # v3.3 INTEGRATION: Use counterfactual-based waterfall
    # =========================================================
    # CRITICAL FIX: Use decision_impact_override if provided (spend-filtered impact)
    # Otherwise fall back to calculating from canonical_metrics

    if decision_impact_override is not None:
        # Use the pre-calculated spend-filtered impact from analytics.py
        decision_impact_value = decision_impact_override
        # st.caption(f"🔧 DEBUG: Using spend-filtered impact: ${decision_impact_value:,.2f}")
    elif canonical_metrics:
        # Legacy fallback (will be wrong if it includes zero-spend actions)
        decision_impact_value = canonical_metrics.attributed_impact
        # st.warning(f"⚠️ Using canonical_metrics: ${decision_impact_value:,.2f} (may include zero-spend)")
    else:
        decision_impact_value = 0.0

    # Calculate v3.5 waterfall using timeline-based ROAS if available
    # (This should already be filtered to active_df with spend > 0)
    wf = calculate_roas_waterfall_v33(impact_df, decision_impact_value, timeline=timeline)

    # Extract values for v3.4 waterfall display
    baseline_roas = wf['baseline_roas']
    actual_roas = wf['actual_roas']

    # v3.4 GROUPED COMPONENTS
    macro_impact = wf['macro_impact']         # External: Market Forces + Market Drag
    micro_impact = wf['micro_impact']         # Internal: CPC + Structural
    optimization_impact = wf['optimization_impact']  # Decisions

    # Detailed breakdown for expander
    market_impact_roas = wf['market_effect']
    market_drag_roas = wf['market_drag']
    market_drag_dollars = wf['market_drag_dollars']
    cpc_impact = wf['cpc_effect']
    scale_effect = wf['scale_effect']
    portfolio_effect = wf['portfolio_effect']
    structural_total = wf['structural_total']
    unexplained = wf['residual']

    # Metrics for display
    market_shift = wf['market_shift']
    spc_change_pct = wf['spc_change_pct']
    cpc_change_pct = wf['cpc_change_pct']
    
    # Labels (v3.4)
    prior_label = "Baseline"
    final_label = "Final ROAS"

    # Bar Colors
    C_BASELINE = "#475569"   # Slate
    C_MACRO_NEG = "#DC2626"  # Red (external headwinds)
    C_MACRO_POS = "#10B981"  # Emerald (external tailwinds)
    C_MICRO_NEG = "#F59E0B"  # Amber (internal drag)
    C_MICRO_POS = "#3B82F6"  # Blue (internal efficiency)
    C_OPTIMIZATION = "#10B981"  # Emerald (Hero - our decisions)
    C_FINAL = "#06B6D4"     # Cyan (Result)

    macro_color = C_MACRO_POS if macro_impact >= 0 else C_MACRO_NEG
    micro_color = C_MICRO_POS if micro_impact >= 0 else C_MICRO_NEG

    x_labels = [prior_label, "Macro\nImpact", "Micro\nImpact", "Optimization\nImpact", "Residual", final_label]
    
    # Bar Values and Bases (v3.4 - 6 bars, includes residual)
    y_vals = []
    bases = []
    colors = []
    borders = []
    text_labels = []

    current_lvl = 0.0

    # 1. Baseline
    y_vals.append(baseline_roas)
    bases.append(0)
    colors.append(C_BASELINE)
    borders.append("rgba(148, 163, 184, 0.2)")
    text_labels.append(f"{baseline_roas:.2f}")
    current_lvl += baseline_roas

    # 2. Macro Impact (External/Market)
    y_vals.append(macro_impact)
    bases.append(current_lvl)
    colors.append(macro_color)
    borders.append("rgba(239, 68, 68, 0.4)" if macro_impact < 0 else "rgba(16, 185, 129, 0.4)")
    text_labels.append(f"{macro_impact:+.2f}")
    current_lvl += macro_impact

    # 3. Micro Impact (Internal/Structural)
    y_vals.append(micro_impact)
    bases.append(current_lvl)
    colors.append(micro_color)
    borders.append("rgba(245, 158, 11, 0.4)" if micro_impact < 0 else "rgba(59, 130, 246, 0.4)")
    text_labels.append(f"{micro_impact:+.2f}")
    current_lvl += micro_impact

    # 4. Optimization Impact (Decisions)
    y_vals.append(optimization_impact)
    bases.append(current_lvl)
    colors.append(C_OPTIMIZATION)
    borders.append("rgba(16, 185, 129, 0.5)")
    text_labels.append(f"{optimization_impact:+.2f}")
    current_lvl += optimization_impact

    # 5. Residual (Unexplained)
    residual_color = "#94A3B8"  # Slate
    y_vals.append(unexplained)
    bases.append(current_lvl)
    colors.append(residual_color)
    borders.append("rgba(148, 163, 184, 0.4)")
    text_labels.append(f"{unexplained:+.2f}")
    current_lvl += unexplained

    # 6. Final ROAS
    y_vals.append(actual_roas)
    bases.append(0)
    colors.append(C_FINAL)
    borders.append("rgba(6, 182, 212, 0.3)")
    text_labels.append(f"{actual_roas:.2f}")
    
    # --- RENDER CHART ---
    fig = go.Figure()
    
    # Main Bars
    fig.add_trace(go.Bar(
        x=x_labels,
        y=y_vals,
        base=bases,
        marker_color=colors,
        marker_line=dict(width=1, color=borders),
        width=0.55,
        text=text_labels,
        textposition='outside',
        textfont=dict(color='white', size=14),
        hoverinfo='x+y+text',
        name=""
    ))
    
    # Connector lines (v3.4 - 5 connectors for 6 bars)
    conn_x = []
    conn_y = []

    # Path 1: Baseline Top to Macro Start
    conn_x.extend([x_labels[0], x_labels[1], None])
    conn_y.extend([baseline_roas, baseline_roas, None])

    # Path 2: Macro End to Micro Start
    macro_end = baseline_roas + macro_impact
    conn_x.extend([x_labels[1], x_labels[2], None])
    conn_y.extend([macro_end, macro_end, None])

    # Path 3: Micro End to Optimization Start
    micro_end = macro_end + micro_impact
    conn_x.extend([x_labels[2], x_labels[3], None])
    conn_y.extend([micro_end, micro_end, None])

    # Path 4: Optimization End to Residual Start
    opt_end = micro_end + optimization_impact
    conn_x.extend([x_labels[3], x_labels[4], None])
    conn_y.extend([opt_end, opt_end, None])

    # Path 5: Residual End to Final Start
    residual_end = opt_end + unexplained
    conn_x.extend([x_labels[4], x_labels[5], None])
    conn_y.extend([residual_end, residual_end, None])
    
    fig.add_trace(go.Scatter(
        x=conn_x,
        y=conn_y,
        mode='lines',
        line=dict(color='rgba(148, 163, 184, 0.4)', width=2, dash='dash'),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Dynamic Zoom (v3.4)
    data_points = [0, baseline_roas, macro_end, micro_end, opt_end, residual_end, actual_roas]
    min_val = min(data_points)
    max_val = max(data_points)
    
    y_range = None
    if max_val > 0:
        zoom_floor = max(0, min_val * 0.5)
        if min_val > 2.0:
            zoom_floor = max(0, min_val - 0.5)
        padding = (max_val - zoom_floor) * 0.15
        y_range = [max(0, zoom_floor - padding), max_val + padding]

    fig.update_layout(
        title="",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, sans-serif", color='#E2E8F0'),
        showlegend=False,
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(148, 163, 184, 0.08)', 
            zeroline=True, 
            zerolinecolor='rgba(148, 163, 184, 0.2)',
            title="ROAS",
            title_font=dict(size=12, color='#94A3B8'),
            tickfont=dict(color='#94A3B8', size=11),
            range=y_range
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#E2E8F0', size=13),
        )
    )
    
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    
    # --- VISUAL EQUATION (v3.4) ---
    equation_html = (
        f"<div style='text-align: center; color: #E2E8F0; font-weight: 600; font-size: 1.05rem; "
        f"padding: 16px; background: rgba(30, 41, 59, 0.3); border-radius: 8px; margin-top: -10px; margin-bottom: 24px;'>"
        f"<span style='color: #94A3B8'>{baseline_roas:.2f}</span> "
        f"{'-' if macro_impact < 0 else '+'} <span style='color: {'#EF4444' if macro_impact < 0 else '#10B981'}'>{abs(macro_impact):.2f}</span> <span style='font-size: 0.8rem; color: #94A3B8'>(Macro)</span> "
        f"{'-' if micro_impact < 0 else '+'} <span style='color: {'#F59E0B' if micro_impact < 0 else '#3B82F6'}'>{abs(micro_impact):.2f}</span> <span style='font-size: 0.8rem; color: #94A3B8'>(Micro)</span> "
        f"{'-' if optimization_impact < 0 else '+'} <span style='color: {'#EF4444' if optimization_impact < 0 else '#10B981'}'>{abs(optimization_impact):.2f}</span> <span style='font-size: 0.8rem; color: #94A3B8'>(Optimization)</span> "
        f"{'-' if unexplained < 0 else '+'} <span style='color: #94A3B8'>{abs(unexplained):.2f}</span> <span style='font-size: 0.8rem; color: #94A3B8'>(Residual)</span> "
        f"→ <span style='color: #06B6D4'>{actual_roas:.2f} ROAS</span>"
        f"</div>"
    )
    st.markdown(equation_html, unsafe_allow_html=True)
    
    # --- VALUE CREATED BOX (v3.4) ---
    # Use v3.4's pre-calculated counterfactual ROAS
    counterfactual_roas = wf['counterfactual_roas']
    pct_improvement = (optimization_impact / counterfactual_roas) * 100 if counterfactual_roas > 0 else 0

    # IMPORTANT: decision_impact_value should be spend-filtered (excludes zero-spend actions)
    # This correctly represents ROAS contribution from optimization decisions
    if decision_impact_value > 0:
        val_formatted = f"{currency}{decision_impact_value:,.0f}"

        # Debug info
        # st.caption(f"💡 Value Created Calculation: ${decision_impact_value:,.2f} ÷ ${wf['total_spend']:,.2f} = {optimization_impact:+.3f} ROAS")
        
        value_box_html = (
            f'<div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%); '
            f'border: 2px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 28px 32px; '
            f'box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3); margin-top: 24px; margin-bottom: 24px; text-align: center;">'
            f'<div style="color: #10B981; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 12px;">VALUE CREATED</div>'
            f'<div style="color: #10B981; font-size: 2.5rem; font-weight: 800; letter-spacing: -1px; line-height: 1; margin-bottom: 12px;">{val_formatted}</div>'
            f'<div style="color: #94A3B8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 4px;">Without optimizations, ROAS would have been {counterfactual_roas:.2f}</div>'
            f'<div style="color: #10B981; font-size: 0.9rem; font-weight: 600;">You improved performance by {pct_improvement:.0f}%</div>'
            f'</div>'
        )
        st.markdown(value_box_html, unsafe_allow_html=True)
    
    # --- Full Breakdown Expander ---
    with st.expander("Full Breakdown", expanded=False):
        # Get v3.3 metrics for display
        # Note: In v3.3, we use SPC shift for market forces, not individual CPC/CVR/AOV
        # We display them informationally for user understanding

        col1, col2 = st.columns(2)

        # LEFT COLUMN: Macro & Micro Impact (v3.4)
        with col1:
            st.markdown(f"**Macro Impact (External): {macro_impact:+.2f} ROAS**")
            st.divider()

            # Display market forces using v3.3 SPC-based approach
            st.markdown(f"""
            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Market Forces: {market_impact_roas:+.2f}</div>

            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • Sales-per-click (SPC) {('increased' if spc_change_pct >=0 else 'dropped')} {abs(spc_change_pct):.1f}% →
              <span style="color: {'#ff6b6b' if market_impact_roas < 0 else '#2ed573'}">{market_impact_roas:+.2f} ROAS impact</span><br>
            <span style="font-size: 12px; color: #888888; font-style: italic;">Account-level conversion efficiency shift</span>
            </div>

            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-top: 12px; margin-bottom: 8px;">Market Drag: {market_drag_roas:+.2f}</div>

            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • Actions negatively affected by market →
              <span style="color: {'#ff6b6b' if market_drag_roas < 0 else '#2ed573'}">{market_drag_roas:+.2f} ROAS impact</span><br>
            <span style="font-size: 12px; color: #888888; font-style: italic;">{currency}{market_drag_dollars:,.0f} from market-affected actions</span>
            </div>

            <div style="font-size: 12px; color: #888888; margin-top: 8px;">
            Macro Total: {market_impact_roas:+.2f} {market_drag_roas:+.2f} = {macro_impact:+.2f} ✓
            </div>

            <br>

            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Micro Impact (Internal): {micro_impact:+.2f} ROAS</div>
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • CPC Efficiency: {cpc_impact:+.2f} (Cost per click {('increased' if cpc_change_pct >=0 else 'dropped')} {abs(cpc_change_pct):.1f}%)<br>
            • Structural Effects: {structural_total:+.2f} (Scale + Portfolio)<br>
            <span style="font-size: 12px; color: #888888; font-style: italic;">Internal operational changes</span>
            </div>
            """, unsafe_allow_html=True)

        # RIGHT COLUMN: Optimization Impact (v3.4)
        with col2:
            action_count = 0
            if not impact_df.empty:
                if 'is_mature' in impact_df.columns and 'market_tag' in impact_df.columns:
                    action_count = len(impact_df[(impact_df['is_mature'] == True) & (impact_df['market_tag'] != 'Market Drag')])
                else:
                    action_count = len(impact_df)

            st.markdown(f"**Optimization Impact: {optimization_impact:+.2f} ROAS**")
            st.divider()

            st.markdown(f"""
            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Activity:</div>
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • {action_count} optimization actions executed
            </div>

            <br>

            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">ROAS Contribution:</div>
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • Added {optimization_impact:+.2f} on top of counterfactual baseline<br>
            • Offset combined headwinds of {(macro_impact + micro_impact):+.2f}<br>
            • Net effect: Created {currency}{decision_impact_value:,.0f} in value
            </div>

            <br>

            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Impact Breakdown:</div>
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • Macro (External): {macro_impact:+.2f} ROAS<br>
            • Micro (Internal): {micro_impact:+.2f} ROAS<br>
            • Optimization: {optimization_impact:+.2f} ROAS<br>
            • Total Change: {(macro_impact + micro_impact + optimization_impact):.2f}
            </div>
            """, unsafe_allow_html=True)
            
        # BOTTOM: Attribution Summary Box
        quality_flag = wf['quality_flag']
        quality_color = '#2ed573' if '✓' in quality_flag else '#f59e0b'  # Green or amber

        summary_html = "".join([
            '<div style="background-color: #0f1624; border: 1px solid #2d3748; border-radius: 8px; padding: 20px; margin-top: 20px;">',
            '  <div style="color: #cccccc; font-size: 13px; font-weight: 600; margin-bottom: 10px;">Attribution Summary (v3.4)</div>',
            '  <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">',
            '    <div style="color: #aaaaaa; font-size: 13px;">',
            '      Counterfactual Analysis:<br>',
            f'      Without optimization → <b>{counterfactual_roas:.2f} ROAS</b> (Baseline + Macro + Micro)<br>',
            f'      With optimization → <b>{actual_roas:.2f} ROAS</b> (Actual achieved)',
            '    </div>',
            '  </div>',
            '  <div style="color: #aaaaaa; font-size: 13px; line-height: 1.6; margin-bottom: 15px;">',
            f'    <b>Explanation:</b> Macro forces ({macro_impact:+.2f} ROAS from market conditions and drag), ',
            f'    micro effects ({micro_impact:+.2f} ROAS from CPC and structural changes), ',
            f'    and {action_count} optimization decisions ({optimization_impact:+.2f} ROAS) ',
            '    combined to deliver the final result.',
            '  </div>',
            '  <div style="border-top: 1px solid #2d3748; padding-top: 10px; display: flex; justify-content: space-between; font-size: 12px; color: #888888;">',
            f'    <div>Attribution Quality: <span style="color: {quality_color};">{quality_flag}</span></div>',
            f'    <div>Unexplained residual: {unexplained:+.2f} ROAS ({abs(unexplained/baseline_roas*100) if baseline_roas > 0 else 0:.1f}%)</div>',
            '  </div>',
            '</div>'
        ])
        st.markdown(summary_html, unsafe_allow_html=True)
