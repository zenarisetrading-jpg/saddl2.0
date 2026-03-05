import streamlit as st

def inject_optimizer_css():
    """Injects all CSS styles for the Optimizer Redesign."""
    st.markdown("""
    <style>
    /* =========================================
       PART 1: LANDING PAGE & HERO
       ========================================= */
    .optimizer-hero {
        position: relative;
        padding: 48px 0 32px;
        text-align: center;
    }
    
    /* Subtle radial glow */
    .optimizer-hero::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(45, 212, 191, 0.08) 0%, transparent 70%);
        pointer-events: none;
        z-index: 0;
    }
    
    .hero-content {
        position: relative;
        z-index: 1;
    }

    /* Account Snapshot Card */
    .snapshot-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 20px;
        text-align: left;
    }

    .snapshot-label {
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .snapshot-value {
        font-size: 24px;
        font-weight: 600;
        color: #f1f5f9;
        margin-top: 8px;
    }
    
    /* Strategy Preset Cards */
    .preset-card-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 24px 16px;
        background: rgba(30, 41, 59, 0.3);
        border: 2px solid transparent; /* Default transparent border */
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        height: 100%;
        text-align: center;
    }

    .preset-card-container:hover {
        background: rgba(30, 41, 59, 0.5);
        border-color: rgba(255, 255, 255, 0.1);
    }
    
    /* Selected state handled via inline style or separate class applied dynamically */
    
    .preset-icon {
        font-size: 28px;
        margin-bottom: 12px;
        display: block;
    }

    .preset-name {
        font-size: 16px;
        font-weight: 600;
        color: #f1f5f9;
        text-transform: capitalize;
        margin-bottom: 4px;
        display: block;
    }
    
    .preset-desc {
        font-size: 12px;
        color: #64748b;
        line-height: 1.4;
        display: block;
    }
    
    /* Primary CTA Button */
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #2dd4bf 0%, #14b8a6 100%) !important;
        border: none !important;
        border-radius: 12px !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        padding: 20px 32px !important;
        transition: all 0.2s ease !important;
        color: #0f172a !important; /* Dark text on teal */
    }
    
    div[data-testid="stButton"] button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(45, 212, 191, 0.3) !important;
    }
    
    /* =========================================
       PART 2: RESULTS DASHBOARD
       ========================================= */
       
    /* Save Run Banner */
    .save-run-banner {
        position: relative;
        background: linear-gradient(135deg, rgba(45, 212, 191, 0.15) 0%, rgba(6, 182, 212, 0.1) 100%);
        border: 1px solid rgba(45, 212, 191, 0.4);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 32px;
    }
    
    /* Metric Cards */
    .metric-card-primary {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(30, 41, 59, 0.4) 100%);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 16px;
        padding: 24px;
        height: 100%;
    }

    .metric-card-standard {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Metric Card Text Styles */
    .metric-label {
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
        font-weight: 600;
    }

    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 4px;
    }

    .metric-value-large {
        font-size: 36px;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 4px;
    }

    .metric-subtext {
        font-size: 13px;
        color: #94a3b8;
    }

    .metric-icon {
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    /* Tab Navigation */
    .custom-tab-bar {
        display: flex;
        gap: 8px;
        background: rgba(30, 41, 59, 0.3);
        padding: 6px;
        border-radius: 12px;
        margin-bottom: 24px;
        overflow-x: auto;
    }
    
    /* Hide default Streamlit tabs */
    .stTabs {
        display: none;
    }
    
    </style>
    """, unsafe_allow_html=True)

def render_status_badge(text="Ready to Optimize", active=True):
    """Renders the pulsing status badge."""
    pulse_class = "animate-pulse" if active else ""
    color = "#2dd4bf" if active else "#64748b"
    
    st.markdown(f"""
    <div style="display: inline-flex; align-items: center; gap: 8px; 
                background: rgba(45, 212, 191, 0.1); border: 1px solid rgba(45, 212, 191, 0.3);
                padding: 6px 16px; border-radius: 100px; margin-bottom: 16px;">
        <div style="width: 8px; height: 8px; background: {color}; border-radius: 50%; box-shadow: 0 0 8px {color};"></div>
        <span style="color: #f1f5f9; font-size: 13px; font-weight: 500; letter-spacing: 0.5px;">{text}</span>
    </div>
    """, unsafe_allow_html=True)

# Glassmorphic SVG Icons
ICONS = {
    "shield": """<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="url(#gradient-shield)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <defs>
            <linearGradient id="gradient-shield" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#2dd4bf" />
                <stop offset="100%" stop-color="#06b6d4" />
            </linearGradient>
        </defs>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    </svg>""",
    "bolt": """<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="url(#gradient-bolt)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <defs>
            <linearGradient id="gradient-bolt" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#f59e0b" />
                <stop offset="100%" stop-color="#fbbf24" />
            </linearGradient>
        </defs>
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
    </svg>""",
    "chart": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>""",
    "search": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>""",
    "save": """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#f1f5f9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>"""
}

def get_icon(name):
    return ICONS.get(name, "")

def render_metric_card(label, value, subtext=None, is_primary=False, trend=None, color=None):
    """
    Renders a metric card.

    Args:
        label (str): Label text (uppercase).
        value (str): Main value text.
        subtext (str, optional): Secondary text below value.
        is_primary (bool): If True, renders the large green-themed primary card.
        trend (str, optional): Trend text (e.g. "↑ 12% vs last run").
        color (str, optional): Custom color for the value (e.g., "#22c55e" for green).
    """
    if is_primary:
        # Primary "Waste Prevented" Card
        icon_svg = ICONS.get('shield', '')
        html = f"""<div class="metric-card-primary">
<div style="display: flex; align-items: center; gap: 20px;">
<div class="metric-icon">{icon_svg}</div>
<div style="flex: 1;">
<div style="font-size: 11px; color: #4ade80; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600;">{label}</div>
<div style="font-size: 36px; font-weight: 700; color: #22c55e; margin-bottom: 4px;">{value}</div>
<div style="font-size: 13px; color: #86efac;">{subtext if subtext else ''}</div>
{f'<div style="margin-top: 8px; font-size: 12px; color: #22c55e; font-weight: 600;">{trend}</div>' if trend else ''}
</div>
</div>
</div>"""
    else:
        # Standard Card
        value_color = color if color else "#f1f5f9"
        html = f"""<div class="metric-card-standard">
<div class="metric-label">{label}</div>
<div class="metric-value" style="color: {value_color};">{value}</div>
{f'<div class="metric-subtext">{subtext}</div>' if subtext else ''}
</div>"""
    st.markdown(html, unsafe_allow_html=True)
