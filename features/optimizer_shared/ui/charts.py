import streamlit as st
import plotly.graph_objects as go


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fmt(val: float, currency: str, sign: str = "") -> str:
    """Format a number as compact currency string (e.g. AED9.2K, -INR56.9K)."""
    if abs(val) >= 1_000_000:
        return f"{sign}{currency}{val / 1_000_000:.1f}M"
    elif abs(val) >= 1_000:
        return f"{sign}{currency}{val / 1_000:.1f}K"
    return f"{sign}{currency}{val:,.0f}"


# ─── Spend Reallocation ───────────────────────────────────────────────────────

def render_spend_reallocation_chart(
    total_spend_ref: float,
    neg_spend_saving: float,
    bid_saving: float,
    reallocated: float,
    currency: str = "USD",
) -> None:
    """
    Styled card with horizontal progress-bar rows — matches local app design.
    Rows: Current (gray) | Negatives (red) | Bid Downs (amber) | Reallocated (green)
    Each bar width is proportional to total_spend_ref.
    """
    safe_ref = total_spend_ref if total_spend_ref > 0 else 1

    rows = [
        {
            "label":   "Current",
            "value":   total_spend_ref,
            "pct":     100.0,
            "color":   "#475569",
            "txt_col": "#cbd5e1",
            "prefix":  "",
        },
        {
            "label":   "Negatives",
            "value":   neg_spend_saving,
            "pct":     min(neg_spend_saving / safe_ref * 100, 100),
            "color":   "#ef4444",
            "txt_col": "#ef4444",
            "prefix":  "-",
        },
        {
            "label":   "Bid Downs",
            "value":   bid_saving,
            "pct":     min(bid_saving / safe_ref * 100, 100),
            "color":   "#f59e0b",
            "txt_col": "#f59e0b",
            "prefix":  "-",
        },
        {
            "label":   "Reallocated",
            "value":   reallocated,
            "pct":     min(reallocated / safe_ref * 100, 100),
            "color":   "#22c55e",
            "txt_col": "#22c55e",
            "prefix":  "+",
        },
    ]

    bar_rows_html = ""
    for r in rows:
        label_fmt = _fmt(r["value"], currency, r["prefix"])
        bar_rows_html += f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
          <div style="width:86px;text-align:right;font-size:12px;color:#64748b;
                      white-space:nowrap;flex-shrink:0;">{r['label']}</div>
          <div style="flex:1;background:#1e293b;border-radius:4px;height:8px;overflow:hidden;">
            <div style="width:{r['pct']:.1f}%;background:{r['color']};
                        border-radius:4px;height:100%;
                        transition:width .4s ease;"></div>
          </div>
          <div style="width:76px;text-align:right;font-size:12px;font-weight:600;
                      color:{r['txt_col']};white-space:nowrap;flex-shrink:0;">{label_fmt}</div>
        </div>"""

    html = f"""
    <div style="
      background:#0f172a;
      border:1px solid #1e293b;
      border-radius:16px;
      padding:20px 24px 16px 24px;
    ">
      <div style="font-size:15px;font-weight:600;color:#f1f5f9;margin-bottom:3px;">
        Spend Reallocation
      </div>
      <div style="font-size:12px;color:#475569;margin-bottom:20px;">
        How 14-day spend is being optimized
      </div>
      {bar_rows_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ─── Action Distribution ──────────────────────────────────────────────────────

def render_action_distribution_chart(
    action_count: int,
    bid_count: int,
    neg_count: int,
    harv_count: int,
) -> None:
    """
    Styled card with donut chart — matches local app design.
    Total count in centre, legend with exact counts at bottom.
    Colors: Bids=teal, Negatives=blue, Harvest=amber.
    """
    labels = ["Bids", "Negatives", "Harvest"]
    values = [bid_count, neg_count, harv_count]
    colors = ["#22d3ee", "#3b82f6", "#f59e0b"]

    filtered = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not filtered:
        st.caption("No actions to display.")
        return

    f_labels, f_values, f_colors = zip(*filtered)
    legend_labels = [f"{l} ({v})" for l, v in zip(f_labels, f_values)]

    fig = go.Figure(go.Pie(
        labels=list(f_labels),           # plain labels for legend
        values=list(f_values),
        hole=0.62,
        marker=dict(colors=list(f_colors), line=dict(color="#0f172a", width=2)),
        textinfo="none",                 # no text on segments
        text=[""] * len(f_values),       # explicit empty text safety
        hovertemplate="%{label}: %{value}<extra></extra>",
        customdata=legend_labels,
    ))

    fig.update_layout(
        title=dict(
            text="Action Distribution",
            font=dict(size=15, color="#f1f5f9"),
            x=0, xanchor="left",
            pad=dict(b=4),
        ),
        # All annotations in one place — update_layout(annotations) overwrites add_annotation
        annotations=[
            dict(
                text=f"Breakdown of {action_count} optimization actions",
                xref="paper", yref="paper",
                x=0, y=1.02,
                showarrow=False,
                font=dict(size=11, color="#475569"),
                xanchor="left",
            ),
            dict(
                text=f"<b>{action_count}</b><br>Actions",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=24, color="#f1f5f9"),
                align="center",
            ),
        ],
        height=300,
        margin=dict(t=55, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.08,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#94a3b8"),
            bgcolor="rgba(0,0,0,0)",
            itemsizing="constant",
        ),
    )

    # Override legend labels to include counts
    for i, label in enumerate(legend_labels):
        fig.data[0].labels = tuple(legend_labels)

    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
