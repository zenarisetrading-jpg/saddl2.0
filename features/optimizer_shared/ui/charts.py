import streamlit as st
import plotly.graph_objects as go


def render_spend_reallocation_chart(
    total_spend_ref: float,
    neg_spend_saving: float,
    bid_saving: float,
    reallocated: float,
    currency: str = "USD",
) -> None:
    """Horizontal waterfall chart showing how 14-day spend is being optimised."""
    labels   = ["Current", "Negatives", "Bid Downs", "Reallocated"]
    values   = [total_spend_ref, neg_spend_saving, bid_saving, reallocated]
    colors   = ["#6366f1", "#ef4444", "#f59e0b", "#22c55e"]
    sign_pfx = ["", "-", "-", "+"]
    texts    = [f"{sign_pfx[i]}{currency}{v:,.0f}" for i, v in enumerate(values)]

    fig = go.Figure(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=texts,
        textposition="outside",
        textfont=dict(size=12, color="#e2e8f0"),
        cliponaxis=False,
    ))
    fig.update_layout(
        title=dict(text="Spend Reallocation", font=dict(size=13, color="#94a3b8")),
        annotations=[dict(
            text="How 14-day spend is being optimized",
            xref="paper", yref="paper",
            x=0, y=1.12,
            showarrow=False,
            font=dict(size=11, color="#64748b"),
        )],
        height=220,
        margin=dict(t=55, b=10, l=10, r=100),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        showlegend=False,
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(showgrid=False, autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_action_distribution_chart(
    action_count: int,
    bid_count: int,
    neg_count: int,
    harv_count: int,
) -> None:
    """Donut chart showing distribution of optimizer actions."""
    labels = ["Bids", "Negatives", "Harvest"]
    values = [bid_count, neg_count, harv_count]
    colors = ["#6366f1", "#ef4444", "#22c55e"]

    # Filter out zero values
    filtered = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not filtered:
        st.caption("No actions to display.")
        return

    f_labels, f_values, f_colors = zip(*filtered)

    fig = go.Figure(go.Pie(
        labels=list(f_labels),
        values=list(f_values),
        hole=0.60,
        marker_colors=list(f_colors),
        textinfo="none",
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        customdata=list(f_values),
    ))

    # Count in center of donut
    fig.add_annotation(
        text=f"<b>{action_count}</b><br><span style='font-size:11px;color:#94a3b8'>Actions</span>",
        x=0.5, y=0.5,
        font=dict(size=22, color="#e2e8f0"),
        showarrow=False,
        xref="paper", yref="paper",
    )

    # Legend with exact counts
    legend_labels = [f"{l} ({v})" for l, v in zip(f_labels, f_values)]

    fig.update_traces(
        labels=legend_labels,
    )

    fig.update_layout(
        title=dict(text="Action Distribution", font=dict(size=13, color="#94a3b8")),
        height=280,
        margin=dict(t=40, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
