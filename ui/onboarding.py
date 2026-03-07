"""
Onboarding Wizard for SADDL AdPulse
====================================

3-step welcome experience for new users.

PRD Reference: Automated User Onboarding Implementation Plan - Phase 3

Steps:
1. Welcome & Value Proposition
2. Feature Overview
3. Next Steps / Getting Started

Usage:
    from ui.onboarding import render_onboarding_wizard, should_show_onboarding

    if should_show_onboarding():
        render_onboarding_wizard()
"""

import os
import time

import streamlit as st
from config.design_system import COLORS, TYPOGRAPHY, SPACING, GLASSMORPHIC
from config.features import FEATURE_ONBOARDING_WIZARD
from ui.components.icons import glassmorphic_icon
from utils.amazon_oauth import generate_amazon_oauth_url


def should_show_onboarding() -> bool:
    """
    Check if the onboarding wizard should be shown.

    Returns:
        True if wizard should be shown, False otherwise
    """
    # Feature flag check
    if not FEATURE_ONBOARDING_WIZARD:
        return False

    # Check session state flag
    return st.session_state.get('show_onboarding', False)


def dismiss_onboarding():
    """Mark onboarding as dismissed."""
    st.session_state['show_onboarding'] = False
    st.session_state['onboarding_step'] = 1

    # Optionally save to user preferences in database
    _save_onboarding_preference(completed=True)


def reset_onboarding():
    """Reset onboarding to show again."""
    st.session_state['show_onboarding'] = True
    st.session_state['onboarding_step'] = 1


def _save_onboarding_preference(completed: bool):
    """Save onboarding completion status to user preferences."""
    # This could be extended to save to database
    # For now, just use session state



def render_connect_amazon_account_button(
    client_id: str | None = None,
    key: str | None = None,
    force_new_state: bool = False,
    label: str = "🔗 Connect Amazon Account",
):
    """
    Shared OAuth CTA used by onboarding and existing-account SP-API connection surfaces.
    """
    try:
        auth_url = generate_amazon_oauth_url(client_id=client_id, force_new_state=force_new_state)
        st.link_button(
            label,
            auth_url,
            type="primary",
            use_container_width=True,
        )
    except EnvironmentError:
        # Deployment-safe fallback when OAuth env vars are missing.
        st.button(
            f"{label} (Unavailable)",
            key=key,
            type="primary",
            use_container_width=True,
            disabled=True,
        )
        st.caption("SP-API OAuth is not configured in this environment. Set `SP_API_APPLICATION_ID` to enable this button.")


def render_onboarding_wizard():
    """
    Render the complete onboarding wizard.

    Call this from the main app flow when should_show_onboarding() returns True.
    """
    # Initialize step if not set
    if 'onboarding_step' not in st.session_state:
        st.session_state['onboarding_step'] = 1

    # Apply page styling
    _apply_wizard_styles()

    # Render current step
    current_step = st.session_state['onboarding_step']

    if current_step == 1:
        _render_step_1_welcome()
    elif current_step == 2:
        _render_step_2_features()
    elif current_step == 3:
        _render_step_3_next_steps()
    else:
        # Fallback - complete onboarding
        dismiss_onboarding()
        st.rerun()


def _apply_wizard_styles():
    """Apply glassmorphic styling to the wizard."""
    st.markdown(f"""
        <style>
        /* Page background */
        .stApp {{
            background: {COLORS['background']};
        }}

        /* Container width */
        .block-container {{
            max-width: 900px;
            padding-top: 1rem;
            padding-bottom: 3rem;
        }}

        /* Button styling - consistent sizing */
        .stButton > button {{
            min-height: 48px !important;
            padding: 12px 24px !important;
            font-size: 15px !important;
            font-weight: 500 !important;
            border-radius: 12px !important;
            transition: all 0.3s ease !important;
        }}
        
        .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['primary_light']} 100%) !important;
            color: white !important;
            border: none !important;
        }}

        .stButton > button[kind="primary"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
        }}

        .stButton > button[kind="secondary"] {{
            background: {GLASSMORPHIC['background']} !important;
            color: {COLORS['text_secondary']} !important;
            border: {GLASSMORPHIC['border']} !important;
        }}

        .stButton > button[kind="secondary"]:hover {{
            color: {COLORS['text_primary']} !important;
            border-color: rgba(255, 255, 255, 0.2) !important;
        }}

        /* Tab styling - clean, no emojis needed */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            background: {GLASSMORPHIC['background']};
            padding: 8px;
            border-radius: 16px;
            border: {GLASSMORPHIC['border']};
        }}

        .stTabs [data-baseweb="tab"] {{
            background: transparent;
            border-radius: 10px;
            color: {COLORS['text_secondary']};
            padding: 14px 24px;
            font-weight: 500;
        }}

        .stTabs [aria-selected="true"] {{
            background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['primary_light']} 100%) !important;
            color: white !important;
        }}

        /* Hide Streamlit elements */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)


def _render_step_1_welcome():
    """Render Step 1: Welcome & Value Proposition."""
    # Progress indicator
    _render_progress(1, 3)

    # Hero section with enhanced visuals
    st.html(f"""
        <div style="text-align: center; padding: {SPACING['xl']} 0 {SPACING['lg']} 0;">
            <!-- Large decorative icon -->
            <div style="margin-bottom: {SPACING['lg']};">
                {glassmorphic_icon('welcome', size=120)}
            </div>
            
            <!-- Main heading with gradient text -->
            <h1 style="
                font-size: 56px;
                background: linear-gradient(135deg, #fff 0%, {COLORS['primary_light']} 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                margin: 0 0 {SPACING['md']} 0;
                font-weight: 800;
                font-family: {TYPOGRAPHY['font_family']};
                letter-spacing: -1px;
            ">
                Welcome to SADDL AdPulse
            </h1>
            
            <p style="
                font-size: {TYPOGRAPHY['body_lg']};
                color: {COLORS['text_secondary']};
                max-width: 600px;
                margin: 0 auto {SPACING['xxl']} auto;
                line-height: 1.7;
            ">
                The only PPC platform that shows you the
                <span style="color: {COLORS['primary']}; font-weight: 600;">actual impact</span>
                of every optimization decision.
            </p>
        </div>
    """)

    # Value proposition cards with icons
    col1, col2, col3 = st.columns(3)

    with col1:
        _render_value_card(
            'impact',
            'Decision-First',
            'See which actions actually moved the needle vs. which were noise'
        )

    with col2:
        _render_value_card(
            'shield',
            'Transparent Attribution',
            'White-box measurement you can verify and trust'
        )

    with col3:
        _render_value_card(
            'chart',
            'Proven ROI',
            'Built by a 7-figure seller who needed better PPC tools'
        )

    # Spacer
    st.markdown(f"<div style='height: {SPACING['xxl']};'></div>", unsafe_allow_html=True)

    # Navigation buttons - centered with consistent sizing
    col1, col2, col3 = st.columns([1, 4, 1])

    with col2:
        bcol1, bcol2 = st.columns(2)

        with bcol1:
            if st.button("Skip for now", type="secondary", use_container_width=True, key="skip_1"):
                dismiss_onboarding()
                st.rerun()

        with bcol2:
            if st.button("Get Started →", type="primary", use_container_width=True, key="next_1"):
                st.session_state['onboarding_step'] = 2
                st.rerun()


def _render_step_2_features():
    """Render Step 2: Feature Overview."""
    # Progress indicator
    _render_progress(2, 3)

    # Header with icon
    st.html(f"""
        <div style="text-align: center; padding: {SPACING['lg']} 0 {SPACING['xl']} 0;">
            <div style="margin-bottom: {SPACING['md']};">
                {glassmorphic_icon('rocket', size=80)}
            </div>
            <h1 style="
                font-size: {TYPOGRAPHY['heading_lg']};
                color: {COLORS['text_primary']};
                margin: 0 0 {SPACING['sm']} 0;
                font-weight: 700;
            ">
                What You Can Do with SADDL AdPulse
            </h1>
            <p style="
                font-size: {TYPOGRAPHY['body_md']};
                color: {COLORS['text_secondary']};
            ">
                Explore our powerful features designed to maximize your PPC performance
            </p>
        </div>
    """)

    # Feature tabs (no emojis - clean text only)
    tab1, tab2, tab3 = st.tabs(["Decision Cockpit", "Impact Waterfall", "Optimizer"])

    with tab1:
        st.markdown(f"<div style='height: {SPACING['md']};'></div>", unsafe_allow_html=True)
        _render_feature_panel(
            'dashboard',
            'Decision Cockpit',
            'Your central command center for PPC performance. See everything that matters at a glance.',
            [
                'Real-time campaign performance metrics',
                'AI-powered insights and recommendations',
                'Custom date range analysis',
                'Account-level and campaign-level views'
            ]
        )

    with tab2:
        st.markdown(f"<div style='height: {SPACING['md']};'></div>", unsafe_allow_html=True)
        _render_feature_panel(
            'impact',
            'Impact Waterfall',
            'See exactly how each optimization contributed to your results with transparent attribution.',
            [
                'Visualize the impact of every action',
                'Statistical significance indicators',
                'Before/after comparison views',
                'Export-ready reports for stakeholders'
            ]
        )

    with tab3:
        st.markdown(f"<div style='height: {SPACING['md']};'></div>", unsafe_allow_html=True)
        _render_feature_panel(
            'optimizer',
            'Smart Optimizer',
            'AI-powered bid and budget optimization that shows you the reasoning behind every recommendation.',
            [
                'Harvest keyword opportunities',
                'Negative keyword discovery',
                'Budget allocation suggestions',
                'One-click bulk actions'
            ]
        )

    # Navigation buttons - consistent sizing
    st.markdown(f"<div style='height: {SPACING['xl']};'></div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])

    with col2:
        bcol1, bcol2, bcol3 = st.columns(3)

        with bcol1:
            if st.button("← Back", type="secondary", use_container_width=True, key="back_2"):
                st.session_state['onboarding_step'] = 1
                st.rerun()

        with bcol2:
            if st.button("Skip", type="secondary", use_container_width=True, key="skip_2"):
                dismiss_onboarding()
                st.rerun()

        with bcol3:
            if st.button("Continue →", type="primary", use_container_width=True, key="next_2"):
                st.session_state['onboarding_step'] = 3
                st.rerun()


def _render_step_3_next_steps():
    """Render Step 3: Next Steps / Getting Started."""
    # Progress indicator
    _render_progress(3, 3)

    # Header
    st.html(f"""
        <div style="text-align: center; padding: {SPACING['lg']} 0 {SPACING['xl']} 0;">
            <div style="margin-bottom: {SPACING['md']};">
                {glassmorphic_icon('checkmark', size=80)}
            </div>
            <h1 style="
                font-size: {TYPOGRAPHY['heading_lg']};
                color: {COLORS['text_primary']};
                margin: 0 0 {SPACING['sm']} 0;
                font-weight: 700;
            ">
                You're All Set!
            </h1>
            <p style="
                font-size: {TYPOGRAPHY['body_md']};
                color: {COLORS['text_secondary']};
            ">
                Here's what's next on your journey
            </p>
        </div>
    """)

    # Checklist - render as proper HTML
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Check if Amazon is connected
        is_connected = st.session_state.get('amazon_connected', False)
        
        # Build checklist HTML properly
        checklist_html = _build_checklist_html([
            ('Account created', 'completed'),
            ('Welcome tour completed', 'completed'),
            ('Connect your advertising accounts', 'completed' if is_connected else 'current'),
            ('Run your first optimization', 'pending'),
            ('Review impact results', 'pending'),
        ])
        
        st.html(f"""
            <div style="
                background: {GLASSMORPHIC['background']};
                backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
                border: {GLASSMORPHIC['border']};
                border-radius: {GLASSMORPHIC['border_radius']};
                padding: {SPACING['xl']};
            ">
                <h3 style="
                    color: {COLORS['text_primary']};
                    font-size: {TYPOGRAPHY['heading_sm']};
                    margin: 0 0 {SPACING['lg']} 0;
                    font-weight: 600;
                ">
                    Your Progress
                </h3>
                {checklist_html}
            </div>
        """)

        # Info banner / Action area
        st.markdown(f"<div style='height: {SPACING['md']};'></div>", unsafe_allow_html=True)
        
        if not is_connected:
            st.html(f"""
                <div style="
                    background: {GLASSMORPHIC['background']};
                    backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
                    border-left: 4px solid {COLORS['warning']};
                    border-radius: 8px;
                    padding: {SPACING['md']} {SPACING['lg']};
                    color: {COLORS['text_primary']};
                    font-size: {TYPOGRAPHY['body_md']};
                    margin-bottom: {SPACING['md']};
                ">
                    <strong>Action Required:</strong> Connect your Amazon Advertising account to enable AI optimization and analytics.
                </div>
            """)
            render_connect_amazon_account_button()
        else:
            client_id = st.session_state.get('amazon_client_id', '')
            db_status = _get_backfill_status(client_id) if client_id else 'unknown'

            if db_status == 'active':
                st.html(f"""
                    <div style="
                        background: {GLASSMORPHIC['background']};
                        backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
                        border-left: 4px solid {COLORS['success']};
                        border-radius: 8px;
                        padding: {SPACING['md']} {SPACING['lg']};
                        color: {COLORS['text_primary']};
                        font-size: {TYPOGRAPHY['body_md']};
                    ">
                        <strong>✅ Data ready!</strong> Your 90-day history has been synced.
                        Taking you to the dashboard…
                        <br><span style="color: {COLORS['text_secondary']}; font-size: 0.9em;">Client ID: {client_id}</span>
                    </div>
                """)
                time.sleep(2)
                dismiss_onboarding()
                st.rerun()

            elif db_status == 'backfilling':
                st.html(f"""
                    <div style="
                        background: {GLASSMORPHIC['background']};
                        backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
                        border-left: 4px solid {COLORS['primary']};
                        border-radius: 8px;
                        padding: {SPACING['md']} {SPACING['lg']};
                        color: {COLORS['text_primary']};
                        font-size: {TYPOGRAPHY['body_md']};
                    ">
                        <strong>Syncing your data…</strong> Pulling 90 days of sales &amp; traffic history.
                        This usually takes 3–8 minutes. This page refreshes automatically.
                        <br><span style="color: {COLORS['text_secondary']}; font-size: 0.9em;">Client ID: {client_id}</span>
                    </div>
                """)
                time.sleep(5)
                st.rerun()

            else:
                # status = 'connected' — OAuth done, worker hasn't picked it up yet
                st.html(f"""
                    <div style="
                        background: {GLASSMORPHIC['background']};
                        backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
                        border-left: 4px solid {COLORS['warning']};
                        border-radius: 8px;
                        padding: {SPACING['md']} {SPACING['lg']};
                        color: {COLORS['text_primary']};
                        font-size: {TYPOGRAPHY['body_md']};
                    ">
                        <strong>Connected!</strong> Waiting for the sync worker to start…
                        <br><span style="color: {COLORS['text_secondary']}; font-size: 0.9em;">Client ID: {client_id}</span>
                    </div>
                """)
                time.sleep(5)
                st.rerun()

    # Navigation buttons
    st.markdown(f"<div style='height: {SPACING['xl']};'></div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])

    with col2:
        bcol1, bcol2 = st.columns(2)

        with bcol1:
            if st.button("← Back", type="secondary", use_container_width=True, key="back_3"):
                st.session_state['onboarding_step'] = 2
                st.rerun()

        with bcol2:
            if st.button("Go to Dashboard →", type="primary", use_container_width=True, key="finish"):
                dismiss_onboarding()
                st.rerun()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _render_progress(current: int, total: int):
    """Render progress indicator with dots."""
    dots_html = ""
    for i in range(1, total + 1):
        if i < current:
            dot_style = f"background: {COLORS['primary']}; border-color: {COLORS['primary']};"
        elif i == current:
            dot_style = f"background: {COLORS['primary']}; border-color: {COLORS['primary']}; box-shadow: 0 0 12px {COLORS['primary']};"
        else:
            dot_style = f"background: transparent; border-color: {COLORS['text_muted']};"

        dots_html += f'''
            <div style="
                width: 12px;
                height: 12px;
                border-radius: 50%;
                border: 2px solid;
                {dot_style}
            "></div>
        '''

    progress_pct = (current / total) * 100 if total > 0 else 0

    st.html(f"""
        <div style="margin: {SPACING['lg']} 0 {SPACING['xl']} 0;">
            <div style="
                width: 100%;
                height: 4px;
                background: {GLASSMORPHIC['background']};
                border-radius: 2px;
                overflow: hidden;
                margin-bottom: {SPACING['md']};
            ">
                <div style="
                    width: {progress_pct}%;
                    height: 100%;
                    background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['primary_light']});
                    transition: width 0.5s ease;
                    box-shadow: 0 0 12px {COLORS['primary']};
                "></div>
            </div>
            <div style="
                display: flex;
                justify-content: center;
                gap: {SPACING['md']};
                align-items: center;
            ">
                {dots_html}
            </div>
            <div style="
                text-align: center;
                color: {COLORS['text_muted']};
                font-size: {TYPOGRAPHY['body_sm']};
                margin-top: {SPACING['sm']};
            ">
                Step {current} of {total}
            </div>
        </div>
    """)


def _render_value_card(icon_name: str, title: str, description: str):
    """Render a value proposition card with icon."""
    st.html(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {SPACING['xl']};
            text-align: center;
            height: 100%;
            min-height: 320px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            transition: all 0.3s ease;
        ">
            <div style="margin-bottom: {SPACING['md']}; flex-shrink: 0;">
                {glassmorphic_icon(icon_name, size=56)}
            </div>
            <h3 style="
                color: {COLORS['text_primary']};
                font-size: {TYPOGRAPHY['heading_sm']};
                font-weight: 600;
                margin: 0 0 {SPACING['sm']} 0;
                min-height: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                {title}
            </h3>
            <p style="
                color: {COLORS['text_secondary']};
                font-size: {TYPOGRAPHY['body_md']};
                line-height: 1.6;
                margin: 0;
                flex-grow: 1;
            ">
                {description}
            </p>
        </div>
    ''')


def _render_feature_panel(icon_name: str, title: str, description: str, features: list):
    """Render a feature panel with checklist."""
    features_html = ""
    for feature in features:
        features_html += f'''
            <li style="
                color: {COLORS['text_secondary']};
                margin-bottom: 10px;
                display: flex;
                align-items: flex-start;
                gap: 10px;
            ">
                <span style="color: {COLORS['success']}; font-size: 16px;">✓</span>
                <span>{feature}</span>
            </li>
        '''

    st.html(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {SPACING['xl']};
        ">
            <div style="display: flex; align-items: center; gap: {SPACING['md']}; margin-bottom: {SPACING['md']};">
                {glassmorphic_icon(icon_name, size=48)}
                <h3 style="
                    color: {COLORS['text_primary']};
                    font-size: {TYPOGRAPHY['heading_sm']};
                    font-weight: 600;
                    margin: 0;
                ">
                    {title}
                </h3>
            </div>
            <p style="
                color: {COLORS['text_secondary']};
                font-size: {TYPOGRAPHY['body_md']};
                line-height: 1.6;
                margin-bottom: {SPACING['md']};
            ">
                {description}
            </p>
            <ul style="
                list-style: none;
                padding: 0;
                margin: 0;
                font-size: {TYPOGRAPHY['body_sm']};
            ">
                {features_html}
            </ul>
        </div>
    ''')


def _build_checklist_html(items: list) -> str:
    """Build checklist HTML from items list."""
    html = ""
    for text, status in items:
        if status == 'completed':
            icon = f'<span style="color: {COLORS["success"]}; font-size: 20px;">✓</span>'
            text_style = f"color: {COLORS['text_secondary']}; text-decoration: line-through;"
        elif status == 'current':
            icon = f'<span style="color: {COLORS["primary"]}; font-size: 20px;">●</span>'
            text_style = f"color: {COLORS['text_primary']}; font-weight: 500;"
        else:
            icon = f'<span style="color: {COLORS["text_muted"]}; font-size: 20px;">○</span>'
            text_style = f"color: {COLORS['text_muted']};"

        html += f'''
            <div style="
                display: flex;
                align-items: center;
                gap: {SPACING['md']};
                padding: {SPACING['sm']} 0;
            ">
                {icon}
                <span style="{text_style} font-size: {TYPOGRAPHY['body_md']};">
                    {text}
                </span>
            </div>
        '''
    return html


def _get_backfill_status(client_id: str) -> str:
    """Query DB for the current onboarding_status of a client. Returns 'unknown' on any error."""
    try:
        import psycopg2  # type: ignore
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return "unknown"
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT onboarding_status FROM client_settings WHERE client_id = %s",
                    (client_id,),
                )
                row = cur.fetchone()
        return row[0] if row else "unknown"
    except Exception:
        return "unknown"


# ============================================================================
# UTILITY FUNCTIONS FOR MAIN APP INTEGRATION
# ============================================================================

def get_onboarding_status() -> dict:
    """
    Get the current onboarding status.

    Returns:
        Dictionary with onboarding state info
    """
    return {
        'show_onboarding': st.session_state.get('show_onboarding', False),
        'onboarding_step': st.session_state.get('onboarding_step', 1),
        'onboarding_completed': st.session_state.get('onboarding_completed', False),
    }
