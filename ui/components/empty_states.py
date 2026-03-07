"""
Empty State Components
Reusable empty states for various data scenarios.
"""

import streamlit as st
from ui.components.icons import glassmorphic_icon
from ui.components.glassmorphic import info_banner

import textwrap

import textwrap

def render_empty_state(state_type: str, context: dict = None):
    """
    Render a styled empty state based on the type.
    
    Args:
        state_type: 'no_account', 'no_data', 'filtered_empty'
        context: Optional dictionary with dynamic values (e.g. account_name)
    """
    if context is None:
        context = {}
        
    theme_mode = st.session_state.get('theme_mode', 'dark')
    # Dynamic colors based on theme if needed, but using established design system vars
    
    if state_type == 'no_account':
        _render_no_account_state()
    elif state_type == 'no_data':
        _render_no_data_state(context.get('account_name', 'Account'))
    elif state_type == 'filtered_empty':
        _render_filtered_empty_state()

def _render_no_account_state():
    """Render the 'No Accounts' empty state."""
    st.markdown(textwrap.dedent(f"""
    <div style="
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 60vh;
        text-align: center;
        padding: 40px;
    ">
        <div style="margin-bottom: 32px;">
            {glassmorphic_icon('dashboard', size=120)}
        </div>
        
        <h1 style="
            font-size: 2rem;
            color: #F8FAFC;
            margin-bottom: 16px;
            font-weight: 600;
        ">
            Welcome to SADDL AdPulse!
        </h1>
        
        <p style="
            font-size: 1.1rem;
            color: #94a3b8;
            max-width: 600px;
            margin-bottom: 32px;
            line-height: 1.6;
        ">
            Let's get started by connecting your first advertising account to unlock powerful insights.
        </p>
        
        <div style="display: flex; gap: 16px; justify-content: center; margin-bottom: 40px;">
           <!-- Buttons handled via Streamlit native for functionality -->
        </div>
    </div>
    """).strip().replace('\n', ' '), unsafe_allow_html=True)
    
    # Render buttons outside HTML to keep Streamlit functionality
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("Connect Account", type="primary", use_container_width=True):
            st.session_state['show_account_form'] = True
            st.rerun()

    st.markdown(textwrap.dedent(f"""
    <div style="
        display: flex;
        justify-content: center;
        margin-top: 16px;
    ">
        <div style="max-width: 500px; width: 100%;">
            {info_banner(
                '💡 <strong>Why connect?</strong> SADDL analyzes your campaigns to show verified impact, transparent attribution, and statistical confidence.',
                'info'
            )}
        </div>
    </div>
    """).strip().replace('\n', ' '), unsafe_allow_html=True)

def _render_no_data_state(account_name):
    """Render the 'No Data' empty state (Syncing/Loading similar)."""
    st.markdown(textwrap.dedent(f"""
    <div style="
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 50vh;
        text-align: center;
        padding: 40px;
    ">
        <div style="margin-bottom: 24px;">
            {glassmorphic_icon('connect', size=100)}
        </div>
        
        <h2 style="
            font-size: 1.75rem;
            color: #F8FAFC;
            margin-bottom: 12px;
            font-weight: 600;
        ">
            Setting up {account_name}...
        </h2>
        
        <p style="
            font-size: 1rem;
            color: #94a3b8;
            max-width: 500px;
            margin-bottom: 24px;
            line-height: 1.5;
        ">
            We're syncing your campaign analytics. This usually takes 2-5 minutes.
            Feel free to explore other pages while we work.
        </p>
    </div>
    """).strip().replace('\n', ' '), unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("↻ Check for Data", type="primary", use_container_width=True):
            st.rerun()

def _render_filtered_empty_state():
    """Render 'No Results' for current filters."""
    st.markdown(textwrap.dedent(f"""
    <div style="
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 60px 20px;
        text-align: center;
        background: rgba(30, 41, 59, 0.3);
        border: 1px dashed rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        margin: 20px 0;
    ">
        <div style="margin-bottom: 20px; opacity: 0.7;">
            {glassmorphic_icon('search', size=64)}
        </div>
        
        <h3 style="
            font-size: 1.25rem;
            color: #E2E8F0;
            margin-bottom: 8px;
            font-weight: 600;
        ">
            No data found for selected filters
        </h3>
        
        <p style="
            font-size: 0.95rem;
            color: #94a3b8;
            margin-bottom: 24px;
        ">
            Try expanding your date range or selecting different accounts.
        </p>
    </div>
    """).strip().replace('\n', ' '), unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c2:
        if st.button("Clear Filters", type="secondary", use_container_width=True):
            # Reset common filter keys
            keys_to_reset = ['impact_horizon', 'validated_only_toggle']
            for k in keys_to_reset:
                 if k in st.session_state:
                     del st.session_state[k]
            st.rerun()
