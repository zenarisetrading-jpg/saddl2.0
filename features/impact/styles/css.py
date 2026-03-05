"""
Centralized CSS Styles - Brand colors and component styles.
"""

# Brand color palette
BRAND_COLORS = {
    'purple': '#5B556F',
    'purple_light': '#8F8CA3',
    'cyan': '#22d3ee',
    'cyan_dark': '#06B6D4',
    'green': '#10B981',
    'green_dark': '#059669',
    'red': '#EF4444',
    'red_dark': '#DC2626',
    'gray': '#9CA3AF',
    'slate': '#475569',
    'slate_light': '#64748b',
    'slate_dark': '#334155',
}

# Theme-aware colors
THEME_COLORS = {
    'dark': {
        'bg_primary': 'rgba(15, 23, 42, 0.95)',
        'bg_secondary': 'rgba(30, 41, 59, 0.95)',
        'text_primary': '#F8FAFC',
        'text_secondary': '#94a3b8',
        'text_muted': '#64748b',
        'border': 'rgba(148, 163, 184, 0.15)',
        'border_accent': 'rgba(148, 163, 184, 0.2)',
    },
    'light': {
        'bg_primary': 'rgba(255, 255, 255, 0.95)',
        'bg_secondary': 'rgba(248, 250, 252, 0.95)',
        'text_primary': '#1e293b',
        'text_secondary': '#475569',
        'text_muted': '#94a3b8',
        'border': 'rgba(148, 163, 184, 0.2)',
        'border_accent': 'rgba(148, 163, 184, 0.3)',
    }
}


def get_hero_styles(state: str = 'positive', theme: str = 'dark') -> dict:
    """
    Get hero banner styles based on state (positive/negative/neutral).

    Args:
        state: 'positive', 'negative', or 'neutral'
        theme: 'dark' or 'light'

    Returns:
        dict with CSS properties
    """
    theme_colors = THEME_COLORS[theme]

    if state == 'positive':
        return {
            'bg': f"linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, {theme_colors['bg_primary']} 100%)",
            'border': '1px solid rgba(16, 185, 129, 0.3)',
            'glow': '0 0 30px rgba(16, 185, 129, 0.2)',
            'text_glow': 'text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);',
            'accent_color': BRAND_COLORS['green'],
        }
    elif state == 'negative':
        return {
            'bg': f"linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, {theme_colors['bg_primary']} 100%)",
            'border': '1px solid rgba(239, 68, 68, 0.3)',
            'glow': '0 0 30px rgba(239, 68, 68, 0.2)',
            'text_glow': 'text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);',
            'accent_color': BRAND_COLORS['red'],
        }
    else:  # neutral
        return {
            'bg': f"linear-gradient(135deg, {theme_colors['bg_secondary']} 0%, {theme_colors['bg_primary']} 100%)",
            'border': f"1px solid {theme_colors['border_accent']}",
            'glow': '0 4px 16px rgba(0, 0, 0, 0.3)',
            'text_glow': '',
            'accent_color': BRAND_COLORS['gray'],
        }


def get_card_styles(theme: str = 'dark') -> dict:
    """Get metric card styles."""
    theme_colors = THEME_COLORS[theme]
    return {
        'bg': theme_colors['bg_secondary'],
        'border': theme_colors['border'],
        'text_primary': theme_colors['text_primary'],
        'text_secondary': theme_colors['text_secondary'],
    }


def get_table_styles(theme: str = 'dark') -> dict:
    """Get data table styles."""
    theme_colors = THEME_COLORS[theme]
    return {
        'header_bg': theme_colors['bg_secondary'],
        'row_bg': theme_colors['bg_primary'],
        'row_hover': 'rgba(148, 163, 184, 0.1)',
        'text': theme_colors['text_primary'],
        'border': theme_colors['border'],
    }


def get_chart_styles(theme: str = 'dark') -> dict:
    """Get Plotly chart styles."""
    theme_colors = THEME_COLORS[theme]
    return {
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'gridcolor': 'rgba(128,128,128,0.15)',
        'tickfont_color': theme_colors['text_secondary'],
        'title_color': theme_colors['text_primary'],
        # Chart-specific colors
        'positive_color': BRAND_COLORS['green'],
        'negative_color': BRAND_COLORS['red'],
        'neutral_color': BRAND_COLORS['purple'],
        'accent_color': BRAND_COLORS['cyan'],
    }
