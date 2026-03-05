"""
Glassmorphic SVG Icons for SADDL AdPulse
=========================================

Custom SVG icons with glassmorphic styling for consistent visual language.

Usage:
    from ui.components.icons import glassmorphic_icon

    # In Streamlit:
    st.markdown(glassmorphic_icon('welcome', size=64), unsafe_allow_html=True)

Available icons:
    - welcome: Friendly face for welcome screens
    - dashboard: Grid layout for dashboard features
    - impact: Line chart for impact/analytics
    - optimizer: Target/settings for optimizer features
    - connect: Connection nodes for integrations
    - email: Envelope for email features
    - checkmark: Success indicator
    - warning: Alert triangle
    - loading: Animated spinner
    - rocket: Launch/start icon
    - chart: Bar chart for reports
    - shield: Security/protection
"""

from config.design_system import COLORS, GLASSMORPHIC


def glassmorphic_icon(icon_name: str, size: int = 64, color: str = None) -> str:
    """
    Generate a glassmorphic SVG icon.

    Args:
        icon_name: Name of the icon to render
        size: Size in pixels (width and height)
        color: Optional color override (defaults to primary brand color)

    Returns:
        HTML string containing the SVG icon
    """
    if color is None:
        color = COLORS['primary']

    accent = COLORS.get('accent', COLORS['primary_light'])
    success = COLORS['success']
    warning = COLORS['warning']
    surface = GLASSMORPHIC['background']

    # Icon definitions with gradient IDs unique per icon
    icons = {
        'welcome': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_welcome" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="30" fill="{surface}" stroke="url(#grad_welcome)" stroke-width="2"/>
                <path d="M20 28 Q32 20 44 28" stroke="url(#grad_welcome)" stroke-width="2.5" stroke-linecap="round" fill="none"/>
                <circle cx="24" cy="32" r="2.5" fill="url(#grad_welcome)"/>
                <circle cx="40" cy="32" r="2.5" fill="url(#grad_welcome)"/>
                <path d="M22 40 Q32 48 42 40" stroke="url(#grad_welcome)" stroke-width="2.5" stroke-linecap="round" fill="none"/>
            </svg>
        ''',

        'dashboard': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_dashboard" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <rect x="10" y="10" width="20" height="20" rx="4" fill="{surface}" stroke="url(#grad_dashboard)" stroke-width="2"/>
                <rect x="34" y="10" width="20" height="20" rx="4" fill="{surface}" stroke="url(#grad_dashboard)" stroke-width="2"/>
                <rect x="10" y="34" width="20" height="20" rx="4" fill="{surface}" stroke="url(#grad_dashboard)" stroke-width="2"/>
                <rect x="34" y="34" width="20" height="20" rx="4" fill="{surface}" stroke="url(#grad_dashboard)" stroke-width="2"/>
            </svg>
        ''',

        'impact': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_impact" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <path d="M10 50 L22 38 L32 44 L44 26 L54 30" stroke="url(#grad_impact)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                <circle cx="22" cy="38" r="4" fill="url(#grad_impact)"/>
                <circle cx="32" cy="44" r="4" fill="url(#grad_impact)"/>
                <circle cx="44" cy="26" r="4" fill="url(#grad_impact)"/>
                <circle cx="54" cy="30" r="4" fill="url(#grad_impact)"/>
                <path d="M48 14 L54 14 L54 20" stroke="url(#grad_impact)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',

        'optimizer': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_optimizer" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="22" fill="{surface}" stroke="url(#grad_optimizer)" stroke-width="2"/>
                <circle cx="32" cy="32" r="14" fill="none" stroke="url(#grad_optimizer)" stroke-width="2" stroke-dasharray="4 4"/>
                <circle cx="32" cy="32" r="6" fill="url(#grad_optimizer)"/>
                <path d="M32 6 L32 14" stroke="url(#grad_optimizer)" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M32 50 L32 58" stroke="url(#grad_optimizer)" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M6 32 L14 32" stroke="url(#grad_optimizer)" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M50 32 L58 32" stroke="url(#grad_optimizer)" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
        ''',

        'connect': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_connect" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="16" cy="16" r="10" fill="{surface}" stroke="url(#grad_connect)" stroke-width="2"/>
                <circle cx="48" cy="48" r="10" fill="{surface}" stroke="url(#grad_connect)" stroke-width="2"/>
                <circle cx="48" cy="16" r="6" fill="{surface}" stroke="url(#grad_connect)" stroke-width="2"/>
                <circle cx="16" cy="48" r="6" fill="{surface}" stroke="url(#grad_connect)" stroke-width="2"/>
                <path d="M24 22 L42 42" stroke="url(#grad_connect)" stroke-width="2" stroke-linecap="round" stroke-dasharray="4 4"/>
                <path d="M22 16 L42 16" stroke="url(#grad_connect)" stroke-width="2" stroke-linecap="round" stroke-dasharray="4 4"/>
                <path d="M16 22 L16 42" stroke="url(#grad_connect)" stroke-width="2" stroke-linecap="round" stroke-dasharray="4 4"/>
            </svg>
        ''',

        'email': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_email" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <rect x="8" y="16" width="48" height="32" rx="4" fill="{surface}" stroke="url(#grad_email)" stroke-width="2"/>
                <path d="M8 20 L32 36 L56 20" stroke="url(#grad_email)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',

        'checkmark': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_checkmark" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{success};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{color};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="28" fill="{surface}" stroke="url(#grad_checkmark)" stroke-width="2"/>
                <path d="M18 32 L28 42 L46 24" stroke="url(#grad_checkmark)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',

        'warning': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_warning" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{warning};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:#ef4444;stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <path d="M32 8 L58 52 L6 52 Z" fill="{surface}" stroke="url(#grad_warning)" stroke-width="2" stroke-linejoin="round"/>
                <path d="M32 22 L32 36" stroke="url(#grad_warning)" stroke-width="3.5" stroke-linecap="round"/>
                <circle cx="32" cy="44" r="2.5" fill="url(#grad_warning)"/>
            </svg>
        ''',

        'rocket': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_rocket" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <path d="M32 8 C32 8 48 16 48 32 C48 48 32 56 32 56 C32 56 16 48 16 32 C16 16 32 8 32 8 Z" fill="{surface}" stroke="url(#grad_rocket)" stroke-width="2"/>
                <circle cx="32" cy="28" r="6" fill="url(#grad_rocket)"/>
                <path d="M24 48 L20 58 L28 52" stroke="url(#grad_rocket)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                <path d="M40 48 L44 58 L36 52" stroke="url(#grad_rocket)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',

        'chart': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_chart" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <rect x="10" y="34" width="10" height="20" rx="2" fill="url(#grad_chart)" opacity="0.6"/>
                <rect x="27" y="22" width="10" height="32" rx="2" fill="url(#grad_chart)" opacity="0.8"/>
                <rect x="44" y="10" width="10" height="44" rx="2" fill="url(#grad_chart)"/>
            </svg>
        ''',

        'shield': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_shield" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <path d="M32 6 L52 14 L52 30 C52 44 42 54 32 58 C22 54 12 44 12 30 L12 14 L32 6 Z" fill="{surface}" stroke="url(#grad_shield)" stroke-width="2"/>
                <path d="M24 32 L30 38 L42 26" stroke="url(#grad_shield)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',

        'loading': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad_loading" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{accent};stop-opacity:0" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="26" stroke="url(#grad_loading)" stroke-width="4" stroke-linecap="round" fill="none" stroke-dasharray="130 50">
                    <animateTransform attributeName="transform" type="rotate" from="0 32 32" to="360 32 32" dur="1.2s" repeatCount="indefinite"/>
                </circle>
            </svg>
        ''',
    }

    import textwrap
    icon_str = icons.get(icon_name, icons['welcome'])
    return textwrap.dedent(icon_str).strip()


def get_available_icons() -> list:
    """Return list of available icon names."""
    return [
        'welcome', 'dashboard', 'impact', 'optimizer', 'connect',
        'email', 'checkmark', 'warning', 'rocket', 'chart', 'shield', 'loading'
    ]
