"""
Premium Loading Components
High-quality, professional loading states for Saddle UI
"""

import streamlit as st


def render_premium_loader(message: str = "Loading dashboard data...", show_progress: bool = True):
    """
    Renders a premium, professional loading state with animated spinner.

    Args:
        message: Loading message to display
        show_progress: Whether to show animated progress dots
    """
    st.markdown(f"""
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}

    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.4; }}
    }}

    @keyframes shimmer {{
        0% {{ background-position: -1000px 0; }}
        100% {{ background-position: 1000px 0; }}
    }}

    @keyframes dots {{
        0%, 20% {{ content: '.'; }}
        40% {{ content: '..'; }}
        60%, 100% {{ content: '...'; }}
    }}

    .premium-loader-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 400px;
        padding: 60px 20px;
    }}

    .loader-spinner {{
        width: 64px;
        height: 64px;
        border: 4px solid rgba(148, 163, 184, 0.1);
        border-top: 4px solid #06B6D4;
        border-radius: 50%;
        animation: spin 1s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite;
        margin-bottom: 32px;
        box-shadow:
            0 0 20px rgba(6, 182, 212, 0.2),
            inset 0 0 20px rgba(6, 182, 212, 0.1);
    }}

    .loader-message {{
        color: #cbd5e1;
        font-size: 1rem;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-align: center;
        animation: pulse 2s ease-in-out infinite;
    }}

    .loader-progress {{
        display: inline-block;
        width: 20px;
        text-align: left;
    }}

    .loader-progress::after {{
        content: '.';
        animation: dots 1.5s steps(3, end) infinite;
    }}

    .loader-subtitle {{
        color: #64748b;
        font-size: 0.85rem;
        margin-top: 12px;
        text-align: center;
    }}

    /* Skeleton shimmer for cards */
    .skeleton-card {{
        background: linear-gradient(
            90deg,
            rgba(30, 41, 59, 0.4) 0%,
            rgba(51, 65, 85, 0.5) 50%,
            rgba(30, 41, 59, 0.4) 100%
        );
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
        border-radius: 16px;
        height: 220px;
        margin-bottom: 24px;
        border: 1px solid rgba(148, 163, 184, 0.1);
    }}
    </style>

    <div class="premium-loader-container">
        <div class="loader-spinner"></div>
        <div class="loader-message">
            {message}
            {'<span class="loader-progress"></span>' if show_progress else ''}
        </div>
        <div class="loader-subtitle">
            Preparing your performance insights
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_cockpit_skeleton():
    """
    Renders skeleton loader for Decision Cockpit cards.
    Shows the structure immediately while data loads.
    """
    st.markdown("""
    <style>
    @keyframes shimmer {
        0% { background-position: -1000px 0; }
        100% { background-position: 1000px 0; }
    }

    .skeleton-container {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 24px;
        margin-top: 24px;
    }

    .skeleton-card {
        background: linear-gradient(
            135deg,
            rgba(30, 41, 59, 0.6) 0%,
            rgba(15, 23, 42, 0.6) 100%
        );
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 16px;
        padding: 24px;
        min-height: 240px;
        position: relative;
        overflow: hidden;
    }

    .skeleton-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(
            90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.08) 50%,
            transparent 100%
        );
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
    }

    .skeleton-label {
        width: 100px;
        height: 14px;
        background: rgba(148, 163, 184, 0.2);
        border-radius: 4px;
        margin-bottom: 20px;
    }

    .skeleton-circle {
        width: 140px;
        height: 140px;
        border-radius: 50%;
        background: rgba(148, 163, 184, 0.1);
        margin: 20px auto;
    }

    .skeleton-value {
        width: 120px;
        height: 48px;
        background: rgba(148, 163, 184, 0.15);
        border-radius: 8px;
        margin: 32px auto 12px;
    }

    .skeleton-text {
        width: 80px;
        height: 12px;
        background: rgba(148, 163, 184, 0.15);
        border-radius: 4px;
        margin: 8px auto;
    }

    .skeleton-row {
        display: flex;
        justify-content: space-around;
        margin-top: 20px;
    }

    .skeleton-stat {
        text-align: center;
    }

    .skeleton-stat-value {
        width: 40px;
        height: 20px;
        background: rgba(148, 163, 184, 0.15);
        border-radius: 4px;
        margin: 0 auto 6px;
    }

    .skeleton-stat-label {
        width: 30px;
        height: 10px;
        background: rgba(148, 163, 184, 0.1);
        border-radius: 3px;
        margin: 0 auto;
    }

    @media (max-width: 768px) {
        .skeleton-container {
            grid-template-columns: 1fr;
        }
    }
    </style>

    <div class="skeleton-container">
        <!-- Health Score Card -->
        <div class="skeleton-card">
            <div class="skeleton-label"></div>
            <div class="skeleton-circle"></div>
            <div class="skeleton-row">
                <div class="skeleton-stat">
                    <div class="skeleton-stat-value"></div>
                    <div class="skeleton-stat-label"></div>
                </div>
                <div class="skeleton-stat">
                    <div class="skeleton-stat-value"></div>
                    <div class="skeleton-stat-label"></div>
                </div>
                <div class="skeleton-stat">
                    <div class="skeleton-stat-value"></div>
                    <div class="skeleton-stat-label"></div>
                </div>
            </div>
        </div>

        <!-- Decision Impact Card -->
        <div class="skeleton-card">
            <div class="skeleton-label"></div>
            <div class="skeleton-value"></div>
            <div class="skeleton-text"></div>
        </div>

        <!-- Next Step Card -->
        <div class="skeleton-card">
            <div class="skeleton-label"></div>
            <div class="skeleton-value" style="height: 40px; margin-top: 40px;"></div>
            <div class="skeleton-text" style="width: 140px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_inline_loader(message: str = "Loading..."):
    """
    Compact inline loader for smaller components.

    Args:
        message: Loading message
    """
    st.markdown(f"""
    <style>
    .inline-loader {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        color: #94a3b8;
        font-size: 0.9rem;
    }}

    .inline-spinner {{
        width: 20px;
        height: 20px;
        border: 2px solid rgba(148, 163, 184, 0.2);
        border-top: 2px solid #06B6D4;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }}
    </style>

    <div class="inline-loader">
        <div class="inline-spinner"></div>
        <span>{message}</span>
    </div>
    """, unsafe_allow_html=True)


def render_progress_loader(progress: float, message: str = "Processing..."):
    """
    Progress bar loader with percentage.

    Args:
        progress: Progress value 0-100
        message: Loading message
    """
    progress = max(0, min(100, progress))  # Clamp to 0-100

    st.markdown(f"""
    <style>
    .progress-container {{
        padding: 32px;
        text-align: center;
    }}

    .progress-message {{
        color: #cbd5e1;
        font-size: 1rem;
        margin-bottom: 16px;
        font-weight: 500;
    }}

    .progress-bar-wrapper {{
        width: 100%;
        max-width: 400px;
        height: 8px;
        background: rgba(30, 41, 59, 0.6);
        border-radius: 8px;
        margin: 0 auto 12px;
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.1);
    }}

    .progress-bar-fill {{
        height: 100%;
        background: linear-gradient(90deg, #06B6D4 0%, #0891b2 100%);
        border-radius: 8px;
        width: {progress}%;
        transition: width 0.3s ease;
        box-shadow: 0 0 10px rgba(6, 182, 212, 0.4);
    }}

    .progress-percent {{
        color: #64748b;
        font-size: 0.85rem;
        font-weight: 600;
    }}
    </style>

    <div class="progress-container">
        <div class="progress-message">{message}</div>
        <div class="progress-bar-wrapper">
            <div class="progress-bar-fill"></div>
        </div>
        <div class="progress-percent">{progress:.0f}%</div>
    </div>
    """, unsafe_allow_html=True)
