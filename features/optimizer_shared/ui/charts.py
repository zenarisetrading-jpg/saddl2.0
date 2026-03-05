import streamlit as st
import plotly.graph_objects as go


def render_spend_reallocation_chart(
    total_spend_ref: float,
    neg_spend_saving: float,
    bid_saving: float,
    reallocated: float,
    currency: str = "USD",
) -> None:
    """Waterfall chart showing spend reallocation breakdown."""
    labels = ["Total Spend", "Neg Savings", "Bid Savings", "Reallocated"]
    values = [total_spend_ref, -neg_spend_saving, -bid_saving, reallocated]
    colors = ["#6366f1", "#22c55e", "#22c55e", "#f59e0b"]

    fig = go.Figure(go.Bar(
        x=labels,
        y=[total_spend_ref, neg_spend_saving, bid_saving, reallocated],
        marker_color=colors,
        text=[f"{currency} {v:,.0f}" for v in [total_spend_ref, neg_spend_saving, bid_saving, reallocated]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Spend Reallocation",
        height=280,
        margin=dict(t=40, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        showlegend=False,
        yaxis=dict(showgrid=False, visible=False),
        xaxis=dict(showgrid=False),
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
        hole=0.55,
        marker_colors=list(f_colors),
        textinfo="label+percent",
        textfont=dict(size=11),
    ))
    fig.update_layout(
        title=f"Actions ({action_count} total)",
        height=280,
        margin=dict(t=40, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
