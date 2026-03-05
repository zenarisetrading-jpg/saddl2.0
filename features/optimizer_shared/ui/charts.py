import streamlit as st
import math

def render_spend_reallocation_chart(current_spend, negatives_savings, bid_savings, reallocated_spend, currency="₹"):
    """
    Renders the Spend Reallocation Bar Chart using CSS.
    Values should be in currency units.
    """
    # Calculate widths relative to max value for normalization
    max_val = max(current_spend, abs(negatives_savings), abs(bid_savings), abs(reallocated_spend), 1)

    def calc_width(val):
        return min(max(abs(val) / max_val * 100, 1), 100)

    w_current = calc_width(current_spend)
    w_neg = calc_width(negatives_savings)
    w_bid = calc_width(bid_savings)
    w_real = calc_width(reallocated_spend)

    # Format currency
    def fmt(val):
        if abs(val) >= 100000:
            return f"{currency}{abs(val)/100000:.1f}L"
        elif abs(val) >= 1000:
            return f"{currency}{abs(val)/1000:.1f}K"
        else:
            return f"{currency}{abs(val):,.0f}"

    # Use components.html instead of st.markdown for better rendering in columns
    import streamlit.components.v1 as components

    html = f"""
    <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 16px; padding: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #f1f5f9; font-size: 16px; font-weight: 600;">Spend Reallocation</h4>
        <div style="font-size: 12px; color: #94a3b8; margin-bottom: 24px;">How 14-day spend is being optimized</div>

        <!-- Current Spend -->
        <div style="display: grid; grid-template-columns: 100px 1fr 80px; align-items: center; gap: 16px; margin-bottom: 16px;">
            <div style="text-align: right; color: #94a3b8; font-size: 13px;">Current</div>
            <div style="height: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; overflow: hidden;">
                <div style="width: {w_current}%; height: 100%; background: #64748b; border-radius: 5px;"></div>
            </div>
            <div style="font-size: 14px; font-weight: 500; color: #f1f5f9; text-align: right;">{fmt(current_spend)}</div>
        </div>

        <!-- Negatives -->
        <div style="display: grid; grid-template-columns: 100px 1fr 80px; align-items: center; gap: 16px; margin-bottom: 16px;">
            <div style="text-align: right; color: #94a3b8; font-size: 13px;">Negatives</div>
            <div style="height: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; overflow: hidden;">
                <div style="width: {w_neg}%; height: 100%; background: #ef4444; border-radius: 5px;"></div>
            </div>
            <div style="font-size: 14px; font-weight: 500; color: #ef4444; text-align: right;">-{fmt(negatives_savings)}</div>
        </div>

        <!-- Bid Downs -->
        <div style="display: grid; grid-template-columns: 100px 1fr 80px; align-items: center; gap: 16px; margin-bottom: 16px;">
            <div style="text-align: right; color: #94a3b8; font-size: 13px;">Bid Downs</div>
            <div style="height: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; overflow: hidden;">
                <div style="width: {w_bid}%; height: 100%; background: #f59e0b; border-radius: 5px;"></div>
            </div>
            <div style="font-size: 14px; font-weight: 500; color: #f59e0b; text-align: right;">-{fmt(bid_savings)}</div>
        </div>

        <!-- Reallocated -->
        <div style="display: grid; grid-template-columns: 100px 1fr 80px; align-items: center; gap: 16px;">
            <div style="text-align: right; color: #94a3b8; font-size: 13px;">Reallocated</div>
            <div style="height: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; overflow: hidden;">
                <div style="width: {w_real}%; height: 100%; background: #22c55e; border-radius: 5px;"></div>
            </div>
            <div style="font-size: 14px; font-weight: 500; color: #22c55e; text-align: right;">+{fmt(reallocated_spend)}</div>
        </div>
    </div>
    """
    components.html(html, height=280)


def render_action_distribution_chart(total_actions, bids, negatives, harvest):
    """
    Renders the Action Distribution Donut Chart using SVG.
    """
    # Ensure we have valid values
    total = max(total_actions, 1)
    bids = max(bids, 0)
    negatives = max(negatives, 0)
    harvest = max(harvest, 0)

    # Calculate percentages
    p_bids = (bids / total) * 100
    p_neg = (negatives / total) * 100
    p_harv = (harvest / total) * 100

    # SVG donut chart parameters
    # Using a circle with circumference = 2 * pi * r
    # For viewBox="0 0 42 42", we use radius 15.91549430918954 for circumference = 100
    radius = 15.91549430918954
    circumference = 2 * math.pi * radius  # ~100

    # Calculate stroke-dasharray values
    # Each segment is a percentage of the circumference
    dash_bids = p_bids
    dash_neg = p_neg
    dash_harv = p_harv

    # Calculate offsets (cumulative)
    # SVG starts at top (12 o'clock) and goes clockwise
    # We rotate -90deg to start from the right (3 o'clock)
    offset_bids = 0
    offset_neg = -(dash_bids)
    offset_harv = -(dash_bids + dash_neg)

    import streamlit.components.v1 as components

    html = f"""
    <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 16px; padding: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #f1f5f9; font-size: 16px; font-weight: 600;">Action Distribution</h4>
        <div style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;">Breakdown of {total:,} optimization actions</div>

        <div style="position: relative; width: 180px; height: 180px; margin: 0 auto;">
            <svg viewBox="0 0 42 42" style="width: 100%; height: 100%; transform: rotate(-90deg);">
                <!-- Background circle -->
                <circle cx="21" cy="21" r="{radius}" fill="none" stroke="rgba(30, 41, 59, 0.8)" stroke-width="4"></circle>

                <!-- Bids segment (Teal) -->
                <circle cx="21" cy="21" r="{radius}" fill="none" stroke="#2dd4bf" stroke-width="4"
                        stroke-dasharray="{dash_bids} {100 - dash_bids}"
                        stroke-dashoffset="{offset_bids}"
                        stroke-linecap="round"></circle>

                <!-- Negatives segment (Blue) -->
                <circle cx="21" cy="21" r="{radius}" fill="none" stroke="#3b82f6" stroke-width="4"
                        stroke-dasharray="{dash_neg} {100 - dash_neg}"
                        stroke-dashoffset="{offset_neg}"
                        stroke-linecap="round"></circle>

                <!-- Harvest segment (Amber) -->
                <circle cx="21" cy="21" r="{radius}" fill="none" stroke="#f59e0b" stroke-width="4"
                        stroke-dasharray="{dash_harv} {100 - dash_harv}"
                        stroke-dashoffset="{offset_harv}"
                        stroke-linecap="round"></circle>
            </svg>

            <!-- Center text -->
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
                <div style="font-size: 32px; font-weight: 700; color: #f1f5f9; line-height: 1;">{total:,}</div>
                <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Actions</div>
            </div>
        </div>

        <!-- Legend -->
        <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 16px; margin-top: 20px;">
            <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94a3b8;">
                <div style="width: 10px; height: 10px; border-radius: 50%; background: #2dd4bf;"></div>
                <span>Bids ({bids:,})</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94a3b8;">
                <div style="width: 10px; height: 10px; border-radius: 50%; background: #3b82f6;"></div>
                <span>Negatives ({negatives:,})</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94a3b8;">
                <div style="width: 10px; height: 10px; border-radius: 50%; background: #f59e0b;"></div>
                <span>Harvest ({harvest:,})</span>
            </div>
        </div>
    </div>
    """
    components.html(html, height=360)
