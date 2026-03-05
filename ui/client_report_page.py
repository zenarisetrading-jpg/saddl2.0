"""
Client Report Page - Premium Dark Theme
========================================
Matches the main dashboard aesthetic with pure black background.
Glassmorphic cards, gradient accents, premium typography.
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import html
from features.executive_dashboard import ExecutiveDashboard
from features.report_card import ReportCardModule
from app_core.data_hub import DataHub
from utils.formatters import get_account_currency
from ui.theme import ThemeManager
from config.deployment import build_share_url, get_environment, get_display_url
from app_core.db_manager import get_db_manager


def safe_html(text: str) -> str:
    """Escape HTML special characters in user/AI generated content."""
    if not text:
        return ""
    return html.escape(str(text))


# =============================================================================
# GLASSMORPHIC SVG ICONS - Inline for consistent rendering
# =============================================================================

def get_svg_icon(icon_name: str, size: int = 24) -> str:
    """Generate glassmorphic SVG icons matching the dashboard aesthetic."""

    # Color palette matching dashboard
    primary = "#06b6d4"  # Cyan
    emerald = "#10b981"
    amber = "#f59e0b"
    blue = "#3b82f6"

    icons = {
        'star': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="starGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{amber};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#fbbf24;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="url(#starGrad)" stroke="url(#starGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>''',

        'trophy': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="trophyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{emerald};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#34d399;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M6 9H4.5C3.67 9 3 8.33 3 7.5V6C3 5.17 3.67 4.5 4.5 4.5H6" stroke="url(#trophyGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M18 9H19.5C20.33 9 21 8.33 21 7.5V6C21 5.17 20.33 4.5 19.5 4.5H18" stroke="url(#trophyGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M6 4.5H18V11C18 14.31 15.31 17 12 17C8.69 17 6 14.31 6 11V4.5Z" fill="url(#trophyGrad)" fill-opacity="0.2" stroke="url(#trophyGrad)" stroke-width="1.5"/>
            <path d="M12 17V20" stroke="url(#trophyGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M8 21H16" stroke="url(#trophyGrad)" stroke-width="1.5" stroke-linecap="round"/>
        </svg>''',

        'eye': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="eyeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{amber};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#fbbf24;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M2 12C2 12 5 5 12 5C19 5 22 12 22 12C22 12 19 19 12 19C5 19 2 12 2 12Z" fill="url(#eyeGrad)" fill-opacity="0.15" stroke="url(#eyeGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="12" cy="12" r="3" fill="url(#eyeGrad)" stroke="url(#eyeGrad)" stroke-width="1.5"/>
        </svg>''',

        'target': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="targetGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{blue};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#60a5fa;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <circle cx="12" cy="12" r="10" stroke="url(#targetGrad)" stroke-width="1.5" fill="url(#targetGrad)" fill-opacity="0.1"/>
            <circle cx="12" cy="12" r="6" stroke="url(#targetGrad)" stroke-width="1.5" fill="url(#targetGrad)" fill-opacity="0.15"/>
            <circle cx="12" cy="12" r="2" fill="url(#targetGrad)"/>
        </svg>''',

        'brain': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="brainGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{primary};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#22d3ee;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M12 4.5C10.5 4.5 9.5 5.5 9.5 7C9.5 7 8 7 7 8C6 9 6 10.5 6 10.5C5 11 4.5 12 4.5 13C4.5 14.5 5.5 15.5 7 16C7 17.5 8 19 10 19.5V21H14V19.5C16 19 17 17.5 17 16C18.5 15.5 19.5 14.5 19.5 13C19.5 12 19 11 18 10.5C18 10.5 18 9 17 8C16 7 14.5 7 14.5 7C14.5 5.5 13.5 4.5 12 4.5Z" fill="url(#brainGrad)" fill-opacity="0.2" stroke="url(#brainGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M9.5 10C10 10.5 11 10.5 12 10" stroke="url(#brainGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M14.5 10C14 10.5 13 10.5 12 10" stroke="url(#brainGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M12 10V14" stroke="url(#brainGrad)" stroke-width="1.5" stroke-linecap="round"/>
        </svg>''',

        'chart': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="chartGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{primary};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#22d3ee;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M3 3V21H21" stroke="url(#chartGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M7 14L11 10L15 13L21 7" stroke="url(#chartGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M17 7H21V11" stroke="url(#chartGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>''',

        'heart': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="heartGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{emerald};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#34d399;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M20.84 4.61C20.33 4.1 19.72 3.69 19.05 3.41C18.38 3.13 17.66 2.98 16.93 2.98C16.2 2.98 15.48 3.13 14.81 3.41C14.14 3.69 13.53 4.1 13.02 4.61L12 5.64L10.98 4.61C9.95 3.58 8.57 3 7.13 3C5.69 3 4.31 3.58 3.28 4.61C2.25 5.64 1.67 7.02 1.67 8.46C1.67 9.9 2.25 11.28 3.28 12.31L4.3 13.33L12 21L19.7 13.33L20.72 12.31C21.23 11.8 21.64 11.19 21.92 10.52C22.2 9.85 22.35 9.13 22.35 8.4C22.35 7.67 22.2 6.95 21.92 6.28C21.64 5.61 21.23 5 20.72 4.49L20.84 4.61Z" fill="url(#heartGrad)" fill-opacity="0.2" stroke="url(#heartGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>''',

        'grid': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="gridGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{primary};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#22d3ee;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <rect x="3" y="3" width="7" height="7" rx="1.5" fill="url(#gridGrad)" fill-opacity="0.2" stroke="url(#gridGrad)" stroke-width="1.5"/>
            <rect x="14" y="3" width="7" height="7" rx="1.5" fill="url(#gridGrad)" fill-opacity="0.2" stroke="url(#gridGrad)" stroke-width="1.5"/>
            <rect x="3" y="14" width="7" height="7" rx="1.5" fill="url(#gridGrad)" fill-opacity="0.2" stroke="url(#gridGrad)" stroke-width="1.5"/>
            <rect x="14" y="14" width="7" height="7" rx="1.5" fill="url(#gridGrad)" fill-opacity="0.2" stroke="url(#gridGrad)" stroke-width="1.5"/>
        </svg>''',

        'bolt': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="boltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{amber};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#fbbf24;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" fill="url(#boltGrad)" fill-opacity="0.2" stroke="url(#boltGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>''',

        'crosshair': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="crossGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{primary};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#22d3ee;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <circle cx="12" cy="12" r="9" stroke="url(#crossGrad)" stroke-width="1.5" fill="url(#crossGrad)" fill-opacity="0.1"/>
            <path d="M12 3V7" stroke="url(#crossGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M12 17V21" stroke="url(#crossGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M3 12H7" stroke="url(#crossGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M17 12H21" stroke="url(#crossGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="12" cy="12" r="2" fill="url(#crossGrad)"/>
        </svg>''',

        'award': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="awardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{emerald};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#34d399;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <circle cx="12" cy="8" r="6" fill="url(#awardGrad)" fill-opacity="0.2" stroke="url(#awardGrad)" stroke-width="1.5"/>
            <path d="M8.21 13.89L7 23L12 20L17 23L15.79 13.88" stroke="url(#awardGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>''',

        'link': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="linkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{primary};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#22d3ee;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <path d="M10 13C10.4295 13.5741 10.9774 14.0491 11.6066 14.3929C12.2357 14.7367 12.9315 14.9411 13.6467 14.9923C14.3618 15.0435 15.0796 14.9403 15.7513 14.6897C16.4231 14.4392 17.0331 14.047 17.54 13.54L20.54 10.54C21.4508 9.59695 21.9548 8.33394 21.9434 7.02296C21.932 5.71198 21.4061 4.45791 20.479 3.52084C19.5519 2.58378 18.2978 2.04785 16.9868 2.03643C15.6758 2.02501 14.4128 2.52904 13.47 3.43999L11.75 5.14999" stroke="url(#linkGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 11C13.5705 10.4259 13.0226 9.95083 12.3934 9.60706C11.7643 9.26329 11.0685 9.05886 10.3533 9.00765C9.63819 8.95643 8.92037 9.05966 8.24866 9.31023C7.57694 9.5608 6.96693 9.95294 6.45999 10.46L3.45999 13.46C2.54903 14.403 2.04501 15.666 2.05643 16.977C2.06785 18.288 2.59378 19.5421 3.52084 20.4791C4.44791 21.4162 5.70197 21.9521 7.01295 21.9636C8.32393 21.975 9.58694 21.4709 10.53 20.56L12.24 18.85" stroke="url(#linkGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>''',

        'calendar': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="calGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{blue};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#60a5fa;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke="url(#calGrad)" stroke-width="1.5" fill="url(#calGrad)" fill-opacity="0.1"/>
            <line x1="16" y1="2" x2="16" y2="6" stroke="url(#calGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="8" y1="2" x2="8" y2="6" stroke="url(#calGrad)" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="3" y1="10" x2="21" y2="10" stroke="url(#calGrad)" stroke-width="1.5"/>
        </svg>''',

        'settings': f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="setGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{amber};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#fbbf24;stop-opacity:0.7" />
                </linearGradient>
            </defs>
            <circle cx="12" cy="12" r="3" stroke="url(#setGrad)" stroke-width="1.5"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="url(#setGrad)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    }

    return icons.get(icon_name, icons['star'])


# =============================================================================
# STYLES - Premium Dark Theme (Pure Black Background)
# =============================================================================

def inject_premium_styles():
    """
    Premium Dark Theme matching the main dashboard.
    Pure black background with glassmorphic cards.
    """
    st.markdown("""
    <style>
    /* ============================================
       TYPOGRAPHY & COLORS
       ============================================ */

    :root {
        --bg-pure-black: #000000;
        --bg-card: rgba(17, 24, 39, 0.6);
        --bg-card-solid: #0E0C12;
        --bg-card-hover: rgba(17, 24, 39, 0.8);
        --border-subtle: rgba(255, 255, 255, 0.08);
        --border-accent: rgba(255, 255, 255, 0.12);

        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;

        --accent-cyan: #06b6d4;
        --accent-blue: #3b82f6;
        --accent-purple: #8b5cf6;
        --accent-pink: #ec4899;
        --accent-amber: #f59e0b;
        --accent-emerald: #10b981;
        --accent-red: #ef4444;

        --gradient-rainbow: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f59e0b);
        --gradient-cyan: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(59, 130, 246, 0.08) 100%);

        /* System font stack - matches Executive Dashboard */
        --font-primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
    }

    /* ============================================
       GLOBAL STYLES
       ============================================ */

    @media screen {
        .stApp {
            background: var(--bg-pure-black) !important;
            font-family: var(--font-primary) !important;
        }

        .main .block-container {
            max-width: 1400px;
            padding: 2rem 2.5rem 4rem 2.5rem;
        }

        header[data-testid="stHeader"],
        footer,
        #MainMenu {
            display: none !important;
        }
    }

    /* ============================================
       HEADER CARD STYLES
       ============================================ */

    .header-card {
        background: radial-gradient(circle at top right, rgba(30, 27, 38, 0.6) 0%, rgba(20, 18, 26, 0.4) 100%), #0E0C12;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        position: relative;
        overflow: hidden;
    }

    .header-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.5), rgba(59, 130, 246, 0.5), transparent);
    }

    .header-title {
        font-family: var(--font-primary);
        font-size: 1.75rem;
        font-weight: 700;
        background: linear-gradient(180deg, #FFFFFF 0%, #D4D4D8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 12px 0;
        line-height: 1.2;
    }

    .header-meta {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
    }

    .meta-pill {
        background: rgba(255, 255, 255, 0.05);
        padding: 6px 12px;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        font-size: 0.8rem;
        color: #A1A1AA;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .meta-pill .status-dot {
        width: 6px;
        height: 6px;
        background: #10B981;
        border-radius: 50%;
    }

    /* Share Card */
    .share-card {
        background: radial-gradient(circle at top right, rgba(30, 27, 38, 0.6) 0%, rgba(20, 18, 26, 0.4) 100%), #0E0C12;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
    }

    .share-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.3), transparent);
    }

    .share-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #E4E4E7;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .share-desc {
        font-size: 0.85rem;
        font-weight: 500;
        color: #A1A1AA;
        line-height: 1.6;
        flex: 1;
    }

    /* ============================================
       SECTION HEADERS
       ============================================ */

    .section-header {
        display: flex;
        align-items: center;
        gap: 14px;
        margin: 2.5rem 0 1.25rem 0;
    }

    .section-icon-box {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(59, 130, 246, 0.08) 100%);
        border: 1px solid rgba(6, 182, 212, 0.25);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .section-title {
        font-family: var(--font-primary);
        font-size: 1.35rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
        letter-spacing: -0.01em;
    }

    /* ============================================
       AI INSIGHT CARDS - Cyan Gradient
       ============================================ */

    .ai-insight-card {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.12) 0%, rgba(59, 130, 246, 0.08) 100%);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(6, 182, 212, 0.2);
        border-left: 3px solid var(--accent-cyan);
        border-radius: var(--radius-md);
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        position: relative;
    }

    .ai-label {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--accent-cyan);
        margin-bottom: 10px;
    }

    .ai-content {
        font-size: 0.95rem;
        line-height: 1.7;
        color: var(--text-secondary);
        margin: 0;
    }

    /* ============================================
       EXECUTIVE SUMMARY CARDS
       ============================================ */

    .summary-card {
        background: var(--bg-card);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-lg);
        padding: 1.25rem;
        height: 100%;
        transition: all 0.2s ease;
    }

    .summary-card:hover {
        border-color: var(--border-accent);
    }

    .summary-card.achievements {
        border-top: 3px solid var(--accent-emerald);
    }

    .summary-card.monitoring {
        border-top: 3px solid var(--accent-amber);
    }

    .summary-card.nextsteps {
        border-top: 3px solid var(--accent-blue);
    }

    .card-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .card-icon-box {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .card-title {
        font-family: var(--font-primary);
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }

    .summary-item {
        padding: 0.6rem 0;
        padding-left: 0.75rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        font-size: 0.85rem;
        line-height: 1.55;
        color: var(--text-secondary);
    }

    .summary-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }

    .summary-card.achievements .summary-item {
        border-left: 2px solid var(--accent-emerald);
    }

    .summary-card.monitoring .summary-item {
        border-left: 2px solid var(--accent-amber);
    }

    .summary-card.nextsteps .summary-item {
        border-left: 2px solid var(--accent-blue);
    }

    /* ============================================
       SHARE BUTTON STYLING
       ============================================ */

    .share-btn-wrapper {
        margin-top: -24px;
    }

    .share-btn-wrapper button {
        width: 100% !important;
        background: linear-gradient(135deg, #06b6d4 0%, #0ea5e9 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 10px 16px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25) !important;
        transition: all 0.2s ease !important;
    }

    .share-btn-wrapper button:hover {
        background: linear-gradient(135deg, #0891b2 0%, #0284c7 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 16px rgba(6, 182, 212, 0.35) !important;
    }

    /* Popover styling */
    [data-testid="stPopover"] > div {
        background: #1a1a2e !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }

    /* ============================================
       FOOTER
       ============================================ */

    .report-footer {
        text-align: center;
        padding: 2rem;
        margin-top: 3rem;
        border-top: 1px solid var(--border-subtle);
    }

    .footer-text {
        font-size: 0.85rem;
        color: var(--text-muted);
        margin: 0;
    }

    /* ============================================
       PRINT STYLES
       ============================================ */

    @media print {
        header, footer,
        .stApp > header,
        .stButton, .stSelectbox, .stTextInput,
        [data-testid="stSidebar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        .share-card {
            display: none !important;
        }

        * {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        .stApp, .main, body {
            background: white !important;
        }

        .main .block-container {
            max-width: 100% !important;
            padding: 0.5in !important;
        }

        .header-card,
        .ai-insight-card,
        .summary-card {
            background: #f8fafc !important;
            border: 1px solid #e2e8f0 !important;
            color: #1e293b !important;
        }

        .header-title,
        .section-title,
        .card-title {
            color: #1e293b !important;
            -webkit-text-fill-color: #1e293b !important;
        }

        .ai-content,
        .summary-item,
        .meta-pill {
            color: #475569 !important;
        }

        .section-header {
            page-break-before: always;
            margin-top: 1.5rem;
        }

        .section-header:first-of-type {
            page-break-before: avoid;
        }

        .ai-insight-card,
        .summary-card,
        .stPlotlyChart {
            page-break-inside: avoid;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def render_landing_page():
    """
    Premium landing page for report configuration.
    Allows user to select date range and report type before generating.
    """
    from datetime import datetime, timedelta
    
    inject_premium_styles()
    
    # Hero Header
    st.markdown(f'''
    <div class="header-card" style="padding: 48px; text-align: center; margin-bottom: 2.5rem;">
        <div style="margin-bottom: 20px; display: flex; justify-content: center;">
            {get_svg_icon('chart', 64)}
        </div>
        <h1 class="header-title" style="font-size: 2.5rem; margin-bottom: 16px;">
            Performance Report Studio
        </h1>
        <p style="color: var(--text-secondary); font-size: 1.1rem; margin: 0; max-width: 600px; margin-left: auto; margin-right: auto;">
            Generate professional performance analysis with AI-powered insights and decision tracking.
        </p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Configuration Form
    with st.form("report_config_form", clear_on_submit=False):
        
        # Grid Layout for Inputs
        c1, c2 = st.columns([1, 1], gap="large")
        
        with c1:
            # ===== DATE RANGE SECTION =====
            st.markdown(f'''
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1rem;">
                {get_svg_icon('calendar', 24)}
                <span class="section-title" style="font-size: 1.1rem;">Analysis Period</span>
            </div>
            ''', unsafe_allow_html=True)
            
            # Determine default index from session state
            default_preset = st.session_state.get('exec_dash_date_range', 'Last 30 Days')
            preset_options = [
                "Last 7 Days",
                "Last 14 Days",
                "Last 30 Days",
                "Last 60 Days",
                "Last 90 Days",
                "Custom Range"
            ]
            
            try:
                default_index = preset_options.index(default_preset)
            except ValueError:
                default_index = 2  # Default to Last 30 Days if not found

            date_preset = st.selectbox(
                "Select date range",
                preset_options,
                index=default_index,
                label_visibility="collapsed"
            )
            
            # Custom date inputs (conditional)
            custom_start, custom_end = None, None
            if date_preset == "Custom Range":
                sc1, sc2 = st.columns(2)
                with sc1:
                    custom_start = st.date_input(
                        "Start Date",
                        value=datetime.now().date() - timedelta(days=30)
                    )
                with sc2:
                    custom_end = st.date_input(
                        "End Date",
                        value=datetime.now().date()
                    )
            else:
                st.caption(f"Analyze data relative to today ({datetime.now().strftime('%b %d')}).")

        with c2:
            # ===== REPORT TYPE SECTION =====
            st.markdown(f'''
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1rem;">
                {get_svg_icon('settings', 24)}
                <span class="section-title" style="font-size: 1.1rem;">Report Scope</span>
            </div>
            ''', unsafe_allow_html=True)
            
            view_type = st.radio(
                "Select report format",
                [
                    "Executive Summary",
                    "Detailed Analysis"
                ],
                label_visibility="collapsed",
                captions=[
                    "High-level overview (5 sections)",
                    "Complete analysis (7 sections)"
                ]
            )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ===== SUBMIT BUTTON =====
        # Centered button with max width
        col_L, col_btn, col_R = st.columns([1, 2, 1])
        with col_btn:
            submitted = st.form_submit_button(
                "Generate Analysis Report",
                width='stretch',
                type="primary"
            )
        
        if submitted:
            # Calculate date range
            if date_preset == "Custom Range":
                if custom_start and custom_end:
                    if custom_end < custom_start:
                        st.error("⚠️ End date must be after start date")
                        st.stop()
                    start_date = custom_start
                    end_date = custom_end
                else:
                    st.error("⚠️ Please select both start and end dates")
                    st.stop()
            else:
                # Parse preset
                days_map = {
                    "Last 7 Days": 7,
                    "Last 14 Days": 14,
                    "Last 30 Days": 30,
                    "Last 60 Days": 60,
                    "Last 90 Days": 90
                }
                days = days_map.get(date_preset, 30)
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
            
            # Save configuration to session state
            st.session_state['report_config'] = {
                'start_date': start_date,
                'end_date': end_date,
                'view_type': view_type,
                'date_preset': date_preset
            }
            st.session_state['show_client_report'] = True
            
            # Update date_range for display
            date_range_str = f"{start_date.strftime('%b %d')} – {end_date.strftime('%b %d, %Y')}"
            st.session_state['date_range'] = date_range_str
            
            # Clear cached narratives to force regeneration with new dates
            cache_keys = [k for k in st.session_state.keys() if k.startswith('client_report_narratives_')]
            for key in cache_keys:
                del st.session_state[key]
            
            st.rerun()
    
    # Feature Showcase Section
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    f1, f2, f3 = st.columns(3, gap="medium")
    
    with f1:
        st.markdown(f'''
        <div class="summary-card">
            <div class="card-header">
                <div class="card-icon-box">{get_svg_icon('brain', 20)}</div>
                <h3 class="card-title">AI Powered</h3>
            </div>
            <p class="footer-text">Generates natural language insights for every metric, explaining the "why" behind performance.</p>
        </div>
        ''', unsafe_allow_html=True)
        
    with f2:
        st.markdown(f'''
        <div class="summary-card">
            <div class="card-header">
                <div class="card-icon-box">{get_svg_icon('bolt', 20)}</div>
                <h3 class="card-title">Impact Tracking</h3>
            </div>
            <p class="footer-text">Visualizes the ROI of your optimizer decisions with a validated causal timeline.</p>
        </div>
        ''', unsafe_allow_html=True)

    with f3:
        st.markdown(f'''
        <div class="summary-card">
            <div class="card-header">
                <div class="card-icon-box">{get_svg_icon('link', 20)}</div>
                <h3 class="card-title">Secure Sharing</h3>
            </div>
            <p class="footer-text">Create read-only public links for clients/stakeholders valid for 30 days.</p>
        </div>
        ''', unsafe_allow_html=True)


# =============================================================================
# COMPONENT RENDERERS
# =============================================================================

def render_header(date_range: str, show_share: bool = False, share_context: dict = None):
    """Render the report header with integrated share functionality."""
    current_time = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    escaped_date = safe_html(date_range)

    col1, col2 = st.columns([0.78, 0.22], gap="medium")

    with col1:
        st.markdown(f'''
        <div class="header-card" style="padding: 24px;">
            <h1 class="header-title">Account Performance Report</h1>
            <div class="header-meta">
                <span class="meta-pill">📅 {escaped_date}</span>
                <span class="meta-pill"><span class="status-dot"></span>Generated {current_time}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    with col2:
        st.markdown(f'''
        <div class="share-card">
            <div class="share-title">{get_svg_icon('link', 16)} Share Report</div>
            <div class="share-desc">Create a secure read-only link for your team or clients.</div>
        </div>
        ''', unsafe_allow_html=True)

        if show_share and share_context:
            st.markdown('<div class="share-btn-wrapper">', unsafe_allow_html=True)
            if hasattr(st, "popover"):
                with st.popover("🔗 Share Access", width='stretch'):
                    st.markdown("#### Generate Shareable Link")
                    st.caption("Creates a read-only public link valid for 30 days.")
                    if st.button("Create Link", type="primary", width='stretch', key="create_link_btn"):
                        _generate_and_show_link(share_context, date_range)
            else:
                if st.button("🔗 Share Access", key="header_share_btn", width='stretch'):
                    st.session_state['show_share_result'] = True
            st.markdown('</div>', unsafe_allow_html=True)

    # Fallback for older Streamlit without popover
    if not hasattr(st, "popover") and st.session_state.get('show_share_result') and share_context:
        with st.expander("🔗 Generated Link", expanded=True):
            _generate_and_show_link(share_context, date_range)


def _generate_and_show_link(context, date_range):
    """Helper to generate link and show it."""
    try:
        db_manager = get_db_manager()
        narratives = context.get('narratives', {})
        client_id = context.get('client_id')

        metadata = {
            'generated_by': 'client_report_page',
            'environment': get_environment(),
            'timestamp': datetime.now().isoformat(),
            'narratives': narratives
        }

        report_id = db_manager.save_shared_report(
            client_id=client_id,
            date_range=date_range,
            metadata=metadata
        )
        url = build_share_url(report_id)

        st.success("Link generated successfully!", icon="✅")
        st.code(url, language="text")
        st.caption("📋 Link valid for 30 days. Copy and share with your team.")
    except Exception as e:
        st.error(f"Error generating link: {e}")


def render_section_header(icon_name: str, title: str):
    """Render a section header with glassmorphic SVG icon."""
    icon_svg = get_svg_icon(icon_name, 22)
    st.markdown(f'''
    <div class="section-header">
        <div class="section-icon-box">{icon_svg}</div>
        <h2 class="section-title">{safe_html(title)}</h2>
    </div>
    ''', unsafe_allow_html=True)


def render_ai_insight(narrative: str):
    """Render an AI insight card."""
    escaped_narrative = safe_html(narrative)
    brain_icon = get_svg_icon('brain', 16)
    st.markdown(f'''
    <div class="ai-insight-card">
        <div class="ai-label">{brain_icon} AI Analysis</div>
        <p class="ai-content">{escaped_narrative}</p>
    </div>
    ''', unsafe_allow_html=True)


def render_executive_summary(summary: dict):
    """Render the executive summary cards with glassmorphic SVG icons."""
    achievements = summary.get("achievements", ["Analysis complete"])
    areas_to_watch = summary.get("areas_to_watch", ["Review dashboard for details"])
    next_steps = summary.get("next_steps", ["Continue monitoring"])

    col1, col2, col3 = st.columns(3, gap="medium")

    with col1:
        items_html = ''.join([f'<div class="summary-item">{safe_html(item)}</div>' for item in achievements])
        trophy_icon = get_svg_icon('trophy', 24)
        st.markdown(f'''
        <div class="summary-card achievements">
            <div class="card-header">
                <div class="card-icon-box">{trophy_icon}</div>
                <h3 class="card-title">Key Achievements</h3>
            </div>
            {items_html}
        </div>
        ''', unsafe_allow_html=True)

    with col2:
        items_html = ''.join([f'<div class="summary-item">{safe_html(item)}</div>' for item in areas_to_watch])
        eye_icon = get_svg_icon('eye', 24)
        st.markdown(f'''
        <div class="summary-card monitoring">
            <div class="card-header">
                <div class="card-icon-box">{eye_icon}</div>
                <h3 class="card-title">Areas to Monitor</h3>
            </div>
            {items_html}
        </div>
        ''', unsafe_allow_html=True)

    with col3:
        items_html = ''.join([f'<div class="summary-item">{safe_html(item)}</div>' for item in next_steps])
        target_icon = get_svg_icon('target', 24)
        st.markdown(f'''
        <div class="summary-card nextsteps">
            <div class="card-header">
                <div class="card-icon-box">{target_icon}</div>
                <h3 class="card-title">Recommended Next Steps</h3>
            </div>
            {items_html}
        </div>
        ''', unsafe_allow_html=True)


def render_footer():
    """Render the report footer."""
    st.markdown('''
    <div class="report-footer">
        <p class="footer-text">✨ Powered by SADDL AdPulse Decision Intelligence</p>
    </div>
    ''', unsafe_allow_html=True)


# =============================================================================
# ALIGNED RENDERERS (Custom for Report)
# =============================================================================

def _render_match_type_table_aligned(data: dict):
    """Render Match Type table with fixed height to align with chart."""
    df = data['df_current'].copy()
    if df.empty:
        st.info("No data available.")
        return

    group_col = 'Refined Match Type' if 'Refined Match Type' in df.columns else 'Match Type'

    agg_cols = {'Spend': 'sum', 'Sales': 'sum', 'Orders': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
    grouped = df.groupby(group_col).agg(agg_cols).reset_index()

    grouped['ACOS'] = np.where(grouped['Sales'] > 0, grouped['Spend'] / grouped['Sales'] * 100, 0)
    grouped['ROAS'] = np.where(grouped['Spend'] > 0, grouped['Sales'] / grouped['Spend'], 0)
    grouped['CTR'] = np.where(grouped['Impressions'] > 0, grouped['Clicks'] / grouped['Impressions'] * 100, 0)
    grouped['CVR'] = np.where(grouped['Clicks'] > 0, grouped['Orders'] / grouped['Clicks'] * 100, 0)
    grouped['CPC'] = np.where(grouped['Clicks'] > 0, grouped['Spend'] / grouped['Clicks'], 0)

    grouped = grouped[grouped['Spend'] > 0]
    grouped = grouped.sort_values('Spend', ascending=False)

    currency = get_account_currency()
    st.dataframe(
        grouped,
        width='stretch',
        column_config={
            group_col: st.column_config.TextColumn("Match Type"),
            'Spend': st.column_config.NumberColumn(f"Spend", format=f"{currency} %.2f"),
            'Sales': st.column_config.NumberColumn(f"Sales", format=f"{currency} %.2f"),
            'Orders': st.column_config.NumberColumn("Orders", format="%d"),
            'Clicks': st.column_config.NumberColumn("Clicks", format="%d"),
            'Impressions': st.column_config.NumberColumn("Impressions", format="%d"),
            'ACOS': st.column_config.NumberColumn("ACOS", format="%.2f%%"),
            'ROAS': st.column_config.NumberColumn("ROAS", format="%.2fx"),
            'CTR': st.column_config.NumberColumn("CTR", format="%.2f%%"),
            'CVR': st.column_config.NumberColumn("CVR", format="%.2f%%"),
            'CPC': st.column_config.NumberColumn("CPC", format=f"{currency} %.2f"),
        },
        hide_index=True,
        height=450
    )


def _render_spend_breakdown_aligned(data: dict):
    """Render Spend Breakdown chart with fixed height to align with table."""
    df = data['df_current'].copy()
    if df.empty:
        st.info("No data available.")
        return

    group_col = 'Refined Match Type' if 'Refined Match Type' in df.columns else 'Match Type'

    breakdown = df.groupby(group_col).agg({'Spend': 'sum', 'Sales': 'sum'}).reset_index()
    total_spend = breakdown['Spend'].sum()
    total_sales = breakdown['Sales'].sum()

    breakdown['Pct_Spend'] = (breakdown['Spend'] / total_spend * 100).fillna(0)
    breakdown['Pct_Sales'] = (breakdown['Sales'] / total_sales * 100).fillna(0)

    breakdown['Efficiency_Ratio'] = breakdown.apply(
        lambda x: x['Pct_Sales'] / x['Pct_Spend'] if x['Pct_Spend'] > 0 else 0, axis=1
    )

    breakdown = breakdown[breakdown['Spend'] > 0]
    breakdown = breakdown.sort_values('Efficiency_Ratio', ascending=True)

    COLORS = {
        'success': '#10B981', 'teal': '#14B8A6', 'warning': '#F59E0B', 'danger': '#EF4444', 'gray': '#6B7280'
    }

    def get_status(ratio):
        if ratio >= 1.0:
            return "Amplifier", COLORS['success']
        elif 0.75 <= ratio < 1.0:
            return "Balanced", COLORS['teal']
        elif 0.5 <= ratio < 0.75:
            return "Review", COLORS['warning']
        else:
            return "Drag", COLORS['danger']

    breakdown['Color'] = breakdown['Efficiency_Ratio'].apply(lambda x: get_status(x)[1])

    type_names = {
        'AUTO': 'Auto', 'BROAD': 'Broad', 'PHRASE': 'Phrase',
        'EXACT': 'Exact', 'PT': 'Product', 'CATEGORY': 'Category', 'OTHER': 'Other'
    }
    breakdown['DisplayName'] = breakdown[group_col].apply(lambda x: type_names.get(str(x).upper(), str(x).title()))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=breakdown['DisplayName'],
        x=breakdown['Efficiency_Ratio'],
        orientation='h',
        marker_color=breakdown['Color'],
        text=breakdown['Efficiency_Ratio'].apply(lambda x: f"{x:.2f}x"),
        textposition='inside',
        insidetextanchor='end',
        textfont=dict(color='white', weight='bold'),
        hovertemplate=(
            "<b>%{y}</b><br>" +
            "Efficiency: <b>%{x:.2f}x</b><br>" +
            "Spend Share: %{customdata[0]:.1f}%<br>" +
            "Rev Share: %{customdata[1]:.1f}%<br>" +
            "<extra></extra>"
        ),
        customdata=breakdown[['Pct_Spend', 'Pct_Sales']]
    ))

    fig.add_vline(x=1.0, line_width=1, line_dash="dash", line_color=COLORS['gray'],
                  annotation_text="Parity (1.0)", annotation_position="top right")

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=450,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.1)',
            title=dict(text="Efficiency Ratio (Rev % / Spend %)", font=dict(size=10, color='gray')),
            zeroline=False
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color='rgba(255,255,255,0.8)')),
        uniformtext=dict(mode='hide', minsize=10)
    )

    st.plotly_chart(fig, width='stretch')


# =============================================================================
# MAIN RUN FUNCTION
# =============================================================================

def run():
    """
    Client Report Page - Premium Dark Theme with Configuration Landing
    """
    
    # =========================================================================
    # LANDING PAGE CHECK
    # =========================================================================
    if not st.session_state.get('show_client_report', False):
        render_landing_page()
        return
    
    # =========================================================================
    # BACK TO CONFIG BUTTON
    # =========================================================================
    col_back, col_spacer = st.columns([0.2, 0.8])
    with col_back:
        if st.button("← Configure Report", help="Return to configuration page", width='stretch'):
            st.session_state['show_client_report'] = False
            st.rerun()
    
    # =========================================================================
    # REPORT GENERATION
    # =========================================================================
    
    inject_premium_styles()

    assistant = None
    try:
        from features.assistant import AssistantModule
        assistant = AssistantModule()
    except Exception:
        # In some deployments Assistant dependencies may be unavailable.
        # The existing fallback narrative path below will handle this.
        assistant = None

    exec_dash = ExecutiveDashboard()
    report_card = ReportCardModule()
    
    # Get report configuration
    report_config = st.session_state.get('report_config', {})
    view_type = report_config.get('view_type', 'Detailed Analysis')
    
    # Generate narratives - Cache in session state
    cache_key = f"client_report_narratives_{st.session_state.get('active_account_id', 'default')}_v2026_metric_fix"
    
    if cache_key not in st.session_state:
        panels_to_generate = [
            "performance", "health", "portfolio", "impact",
            "actions", "match_type", "executive_summary"
        ]

        with st.spinner("🤖 Generating AI insights..."):
            try:
                if assistant is None:
                    raise RuntimeError("Assistant module unavailable in this deployment")
                # Pass explicit date range to Assistant
                start_date = report_config.get('start_date')
                end_date = report_config.get('end_date')
                
                narratives = assistant.generate_report_narratives(
                    panels_to_generate, 
                    start_date=start_date, 
                    end_date=end_date
                )
                # Only cache if generation succeeded
                st.session_state[cache_key] = narratives
            except Exception as e:
                error_msg = str(e)
                # Show user-friendly error for rate limits
                if "429" in error_msg or "Too Many Requests" in error_msg or "Rate limit" in error_msg:
                    st.warning("⏳ AI service rate limit reached. Using fallback content. Please wait a moment and click 'Regenerate Analysis' to retry.")
                else:
                    st.warning(f"⚠️ AI insights temporarily unavailable: {error_msg}. Using fallback content.")

                # Return fallback narratives without caching
                narratives = {
                    "executive_summary": {
                        "achievements": [
                            "Account performance analyzed across all campaigns",
                            "Optimization opportunities identified and quantified",
                            "Decision impact tracking active and validated"
                        ],
                        "areas_to_watch": [
                            "Review detailed dashboard for specific campaign insights",
                            "Monitor pending optimization implementations"
                        ],
                        "next_steps": [
                            "Execute recommended optimization actions",
                            "Track impact over next 14-60 days",
                            "Schedule performance review meeting"
                        ]
                    },
                    "performance": "Detailed analysis available in full dashboard.",
                    "health": "Detailed analysis available in full dashboard.",
                    "portfolio": "Detailed analysis available in full dashboard.",
                    "impact": "Detailed analysis available in full dashboard.",
                    "actions": "Detailed analysis available in full dashboard.",
                    "match_type": "Detailed analysis available in full dashboard."
                }
    else:
        narratives = st.session_state[cache_key]
    
    # Fetch visual data
    with st.spinner("📊 Loading performance data..."):
        print(f"[CLIENT_REPORT] Fetching exec dashboard data...")
        
        # Pass configured dates for strict alignment
        start_date = report_config.get('start_date')
        end_date = report_config.get('end_date')
        
        exec_data = exec_dash._fetch_data(custom_start=start_date, custom_end=end_date)
        print(f"[CLIENT_REPORT] Exec data result: {exec_data is not None}")

        # Override date_str if configured
        date_str = st.session_state.get('date_range', "Period Unknown")
        if not st.session_state.get('date_range'):
            if exec_data and 'date_range' in exec_data:
                dr = exec_data['date_range']
                if dr.get('start') and dr.get('end'):
                    s = pd.to_datetime(dr['start']).strftime('%b %d')
                    e = pd.to_datetime(dr['end']).strftime('%b %d, %Y')
                    date_str = f"{s} – {e}"

        # Load report card data from database (same as exec dashboard)
        hub = DataHub()

        # Try session data first (uploaded files)
        rc_df = hub.get_enriched_data()
        if rc_df is None:
            rc_df = hub.get_data("search_term_report")

        # If no session data, load from database
        if rc_df is None or rc_df.empty:
            print(f"[CLIENT_REPORT] No session data, loading from database...")
            account_id = st.session_state.get('active_account_id')
            if account_id:
                loaded = hub.load_from_database(account_id)
                if loaded:
                    rc_df = hub.get_enriched_data()
                    if rc_df is None:
                        rc_df = hub.get_data("search_term_report")
                    print(f"[CLIENT_REPORT] Loaded from DB: {len(rc_df) if rc_df is not None else 0} rows")
                else:
                    print(f"[CLIENT_REPORT] Database load failed for account: {account_id}")
            else:
                print(f"[CLIENT_REPORT] No active_account_id in session state")

        print(f"[CLIENT_REPORT] Report card data: {len(rc_df) if rc_df is not None else 0} rows")

        rc_metrics = None
        if rc_df is not None and not rc_df.empty:
            rc_metrics = report_card.analyze(rc_df)

    if not exec_data:
        print(f"[CLIENT_REPORT] No exec_data - showing warning")
        st.warning("⚠️ Data analysis pending. Please ensure data is loaded.")
        return
    
    # Prepare Share Context
    is_shared = st.session_state.get('read_only_mode', False)
    share_context = None
    if not is_shared:
        share_context = {
            'client_id': st.session_state.get('active_account_id'),
            'narratives': st.session_state.get(cache_key, {})
        }
    
    # =========================================================================
    # RENDER HEADER WITH SHARE
    # =========================================================================
    render_header(date_str, show_share=not is_shared, share_context=share_context)
    
    # Regenerate button (for refreshing AI)
    if not is_shared:
        col_reg, col_space = st.columns([0.25, 0.75])
        with col_reg:
            if st.button("🔄 Regenerate Analysis", help="Force refresh AI insights"):
                if cache_key in st.session_state:
                    del st.session_state[cache_key]
                st.rerun()
    
    # Read-only banner
    if is_shared:
        st.info("👁️ You are viewing a shared report (Read-Only Mode)")
    
    # =========================================================================
    # SECTION 1: EXECUTIVE SUMMARY (Always Show)
    # =========================================================================
    render_section_header('star', 'Executive Summary')
    render_executive_summary(narratives.get("executive_summary", {}))
    
    # =========================================================================
    # SECTION 2: PERFORMANCE OVERVIEW (Always Show)
    # =========================================================================
    render_section_header('chart', 'Performance Overview')
    render_ai_insight(narratives.get("performance", "Analysis in progress..."))
    exec_dash._render_kpi_cards(exec_data)
    
    # =========================================================================
    # SECTION 3: ACCOUNT HEALTH (Always Show)
    # =========================================================================
    render_section_header('heart', 'Account Health')
    render_ai_insight(narratives.get("health", "Analysis in progress..."))
    exec_dash._render_gauges(exec_data)
    
    # =========================================================================
    # SECTION 4: PORTFOLIO ANALYSIS (Always Show)
    # =========================================================================
    render_section_header('grid', 'Portfolio Analysis')
    render_ai_insight(narratives.get("portfolio", "Analysis in progress..."))
    
    c1, c2 = st.columns([7, 3])
    with c1:
        exec_dash._render_performance_scatter(exec_data)
    with c2:
        exec_dash._render_quadrant_donut(exec_data)
    
    # =========================================================================
    # SECTION 5: DECISION IMPACT (Always Show if data exists)
    # =========================================================================
    has_decisions = False
    if exec_data and exec_data.get('impact_df') is not None and not exec_data['impact_df'].empty:
        has_decisions = True
    
    if has_decisions:
        render_section_header('bolt', 'Decision Impact')
        render_ai_insight(narratives.get("impact", "Analysis in progress..."))
        
        c1, c2 = st.columns([3, 7])
        with c1:
            exec_dash._render_decision_impact_card(exec_data)
        with c2:
            exec_dash._render_decision_timeline(exec_data)
    
    # =========================================================================
    # DETAILED ANALYSIS ONLY - SECTIONS 6 & 7
    # =========================================================================
    
    if view_type == "Detailed Analysis":
        
        # SECTION 6: MATCH TYPE PERFORMANCE
        render_section_header('crosshair', 'Match Type Performance')
        render_ai_insight(narratives.get("match_type", "Analysis in progress..."))
        
        c1, c2 = st.columns([7, 3])
        with c1:
            _render_match_type_table_aligned(exec_data)
        with c2:
            _render_spend_breakdown_aligned(exec_data)
        
        # SECTION 7: ACTIONS & RESULTS (if data exists)
        has_actions = False
        if rc_metrics and rc_metrics.get('actions'):
            acts = rc_metrics['actions']
            total_actions = sum([
                acts.get('bid_increases', 0),
                acts.get('bid_decreases', 0),
                acts.get('negatives', 0),
                acts.get('harvests', 0)
            ])
            if total_actions > 0:
                has_actions = True
        
        if has_actions:
            render_section_header('award', 'Actions & Results')
            render_ai_insight(narratives.get("actions", "Analysis in progress..."))
            report_card._render_section_2_actions(rc_metrics)
    
    # =========================================================================
    # FOOTER
    # =========================================================================
    render_footer()


if __name__ == "__main__":
    run()
