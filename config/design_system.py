"""
Design System Configuration for SADDL AdPulse

Glassmorphic design tokens extracted from the main application.
Used to ensure visual consistency across all UI components.

Usage:
    from config.design_system import COLORS, TYPOGRAPHY, SPACING, GLASSMORPHIC

    # In Streamlit with st.markdown:
    st.markdown(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            color: {COLORS['text_primary']};
            padding: {SPACING['lg']};
        ">
            Content here
        </div>
    ''', unsafe_allow_html=True)
"""

from typing import Dict

# ============================================================================
# COLOR PALETTE
# ============================================================================
# Premium dark theme with blue accent - matches main SADDL AdPulse app

COLORS: Dict[str, str] = {
    # Primary brand colors
    'primary': '#2563eb',           # Electric blue - main brand color
    'primary_dark': '#1e40af',      # Darker blue for hover states
    'primary_light': '#3b82f6',     # Lighter blue for highlights
    'secondary': '#64748b',         # Slate gray - secondary elements
    'accent': '#3b82f6',            # Accent blue for gradients

    # Background colors (dark theme)
    'background': '#0f172a',        # Deep navy - main background
    'background_light': '#1e293b',  # Lighter navy - cards, elevated surfaces
    'background_elevated': '#334155', # Even lighter - modals, dropdowns

    # Glassmorphic surfaces
    'surface': 'rgba(255, 255, 255, 0.05)',       # Translucent white overlay
    'surface_hover': 'rgba(255, 255, 255, 0.1)',  # Hover state
    'surface_active': 'rgba(255, 255, 255, 0.15)', # Active/pressed state

    # Text hierarchy
    'text_primary': '#f1f5f9',      # Primary text - high contrast
    'text_secondary': '#cbd5e1',    # Secondary text - medium contrast
    'text_muted': '#64748b',        # Muted text - low contrast
    'text_inverse': '#0f172a',      # Dark text on light backgrounds

    # Borders
    'border': 'rgba(255, 255, 255, 0.1)',         # Subtle border
    'border_light': 'rgba(255, 255, 255, 0.05)',  # Very subtle border
    'border_focus': 'rgba(37, 99, 235, 0.5)',     # Focus state border

    # Semantic colors
    'success': '#10b981',           # Green - success states
    'success_light': '#34d399',     # Light green - success backgrounds
    'warning': '#f59e0b',           # Amber - warning states
    'warning_light': '#fbbf24',     # Light amber - warning backgrounds
    'error': '#ef4444',             # Red - error states
    'error_light': '#f87171',       # Light red - error backgrounds
    'info': '#3b82f6',              # Blue - info states
    'info_light': '#60a5fa',        # Light blue - info backgrounds

    # Gradients (CSS values)
    'gradient_primary': 'linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)',
    'gradient_success': 'linear-gradient(135deg, #10b981 0%, #34d399 100%)',
    'gradient_premium': 'linear-gradient(135deg, #1e40af 0%, #7c3aed 100%)',
}


# ============================================================================
# TYPOGRAPHY
# ============================================================================
# System font stack with fallbacks - matches modern app aesthetic

TYPOGRAPHY: Dict[str, str] = {
    # Font family
    'font_family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'font_family_mono': '"SF Mono", "Fira Code", "Fira Mono", Consolas, monospace',

    # Heading sizes
    'heading_xl': '48px',           # Hero headings
    'heading_lg': '36px',           # Page titles
    'heading_md': '28px',           # Section headings
    'heading_sm': '20px',           # Card titles
    'heading_xs': '16px',           # Small headings

    # Body text sizes
    'body_lg': '18px',              # Large body text
    'body_md': '16px',              # Default body text
    'body_sm': '14px',              # Small body text
    'caption': '12px',              # Captions, labels

    # Font weights
    'weight_regular': '400',
    'weight_medium': '500',
    'weight_semibold': '600',
    'weight_bold': '700',

    # Line heights
    'line_height_tight': '1.25',
    'line_height_normal': '1.5',
    'line_height_relaxed': '1.75',

    # Letter spacing
    'letter_spacing_tight': '-0.025em',
    'letter_spacing_normal': '0',
    'letter_spacing_wide': '0.025em',
}


# ============================================================================
# SPACING SCALE
# ============================================================================
# Consistent spacing using 4px base unit

SPACING: Dict[str, str] = {
    'none': '0',
    'xs': '4px',                    # 1 unit
    'sm': '8px',                    # 2 units
    'md': '16px',                   # 4 units
    'lg': '24px',                   # 6 units
    'xl': '32px',                   # 8 units
    'xxl': '48px',                  # 12 units
    'xxxl': '64px',                 # 16 units
    'section': '80px',              # Section gaps
}


# ============================================================================
# GLASSMORPHIC EFFECTS
# ============================================================================
# Premium frosted glass effect - signature SADDL look

GLASSMORPHIC: Dict[str, str] = {
    # Backdrop blur effect
    'backdrop_filter': 'blur(16px) saturate(180%)',
    'backdrop_filter_light': 'blur(8px) saturate(150%)',
    'backdrop_filter_heavy': 'blur(24px) saturate(200%)',

    # Semi-transparent backgrounds
    'background': 'rgba(255, 255, 255, 0.05)',
    'background_light': 'rgba(255, 255, 255, 0.08)',
    'background_heavy': 'rgba(255, 255, 255, 0.12)',

    # Borders
    'border': '1px solid rgba(255, 255, 255, 0.1)',
    'border_light': '1px solid rgba(255, 255, 255, 0.05)',
    'border_focus': '1px solid rgba(37, 99, 235, 0.5)',

    # Border radius
    'border_radius': '16px',
    'border_radius_sm': '8px',
    'border_radius_lg': '24px',
    'border_radius_full': '9999px',

    # Shadows
    'box_shadow': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
    'box_shadow_sm': '0 4px 16px 0 rgba(0, 0, 0, 0.25)',
    'box_shadow_lg': '0 16px 48px 0 rgba(0, 0, 0, 0.45)',
    'box_shadow_glow': '0 0 24px 0 rgba(37, 99, 235, 0.3)',
}


# ============================================================================
# TRANSITIONS & ANIMATIONS
# ============================================================================
# Smooth, premium-feeling transitions

TRANSITIONS: Dict[str, str] = {
    'fast': 'all 0.15s ease',
    'normal': 'all 0.3s ease',
    'slow': 'all 0.5s ease',
    'bounce': 'all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
}


# ============================================================================
# BREAKPOINTS
# ============================================================================
# Responsive design breakpoints

BREAKPOINTS: Dict[str, str] = {
    'sm': '640px',
    'md': '768px',
    'lg': '1024px',
    'xl': '1280px',
    'xxl': '1536px',
}


# ============================================================================
# Z-INDEX SCALE
# ============================================================================
# Consistent layering

Z_INDEX: Dict[str, int] = {
    'base': 0,
    'dropdown': 100,
    'sticky': 200,
    'modal_backdrop': 300,
    'modal': 400,
    'popover': 500,
    'tooltip': 600,
    'toast': 700,
}


# ============================================================================
# COMPONENT PRESETS
# ============================================================================
# Pre-built style dictionaries for common components

class ComponentStyles:
    """Pre-built CSS style strings for common components."""

    @staticmethod
    def card(padding: str = SPACING['lg']) -> str:
        """Glassmorphic card container."""
        return f"""
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {padding};
            box-shadow: {GLASSMORPHIC['box_shadow']};
        """

    @staticmethod
    def button_primary() -> str:
        """Primary action button."""
        return f"""
            background: {COLORS['gradient_primary']};
            color: {COLORS['text_primary']};
            border: none;
            border-radius: 12px;
            padding: 14px 32px;
            font-size: {TYPOGRAPHY['body_md']};
            font-weight: {TYPOGRAPHY['weight_semibold']};
            cursor: pointer;
            transition: {TRANSITIONS['normal']};
        """

    @staticmethod
    def button_secondary() -> str:
        """Secondary action button."""
        return f"""
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            color: {COLORS['text_primary']};
            border: {GLASSMORPHIC['border']};
            border-radius: 12px;
            padding: 14px 32px;
            font-size: {TYPOGRAPHY['body_md']};
            font-weight: {TYPOGRAPHY['weight_semibold']};
            cursor: pointer;
            transition: {TRANSITIONS['normal']};
        """

    @staticmethod
    def input_field() -> str:
        """Text input field."""
        return f"""
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: 12px;
            color: {COLORS['text_primary']};
            padding: 12px 16px;
            font-size: {TYPOGRAPHY['body_md']};
            width: 100%;
            transition: {TRANSITIONS['fast']};
        """

    @staticmethod
    def heading(level: str = 'lg') -> str:
        """Heading text styles."""
        size_map = {
            'xl': TYPOGRAPHY['heading_xl'],
            'lg': TYPOGRAPHY['heading_lg'],
            'md': TYPOGRAPHY['heading_md'],
            'sm': TYPOGRAPHY['heading_sm'],
        }
        return f"""
            color: {COLORS['text_primary']};
            font-size: {size_map.get(level, TYPOGRAPHY['heading_lg'])};
            font-weight: {TYPOGRAPHY['weight_bold']};
            line-height: {TYPOGRAPHY['line_height_tight']};
            margin: 0;
        """

    @staticmethod
    def body_text(variant: str = 'primary') -> str:
        """Body text styles."""
        color_map = {
            'primary': COLORS['text_primary'],
            'secondary': COLORS['text_secondary'],
            'muted': COLORS['text_muted'],
        }
        return f"""
            color: {color_map.get(variant, COLORS['text_primary'])};
            font-size: {TYPOGRAPHY['body_md']};
            line-height: {TYPOGRAPHY['line_height_normal']};
        """


# ============================================================================
# STREAMLIT CUSTOM CSS
# ============================================================================
# CSS to inject into Streamlit pages for consistent styling

STREAMLIT_CUSTOM_CSS = f"""
<style>
    /* Global app styling */
    .stApp {{
        background: {COLORS['background']};
        color: {COLORS['text_primary']};
        font-family: {TYPOGRAPHY['font_family']};
    }}

    /* Input field styling */
    .stTextInput input,
    .stSelectbox select,
    .stTextArea textarea {{
        background: {GLASSMORPHIC['background']} !important;
        backdrop-filter: {GLASSMORPHIC['backdrop_filter']} !important;
        border: {GLASSMORPHIC['border']} !important;
        border-radius: 12px !important;
        color: {COLORS['text_primary']} !important;
        padding: 12px 16px !important;
        font-size: {TYPOGRAPHY['body_md']} !important;
    }}

    .stTextInput input:focus,
    .stSelectbox select:focus,
    .stTextArea textarea:focus {{
        border-color: {COLORS['border_focus']} !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
    }}

    /* Primary button styling */
    .stButton > button[kind="primary"],
    .stButton > button {{
        background: {COLORS['gradient_primary']} !important;
        color: {COLORS['text_primary']} !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 32px !important;
        font-weight: {TYPOGRAPHY['weight_semibold']} !important;
        transition: {TRANSITIONS['normal']} !important;
    }}

    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.3);
    }}

    /* Secondary button styling */
    .stButton > button[kind="secondary"] {{
        background: {GLASSMORPHIC['background']} !important;
        border: {GLASSMORPHIC['border']} !important;
    }}

    /* Expander styling */
    .streamlit-expanderHeader {{
        background: {GLASSMORPHIC['background']} !important;
        border: {GLASSMORPHIC['border']} !important;
        border-radius: {GLASSMORPHIC['border_radius_sm']} !important;
    }}

    /* Checkbox styling */
    .stCheckbox label {{
        color: {COLORS['text_primary']} !important;
    }}

    /* Info/warning/error boxes */
    .stAlert {{
        background: {GLASSMORPHIC['background']} !important;
        border-radius: {GLASSMORPHIC['border_radius_sm']} !important;
    }}
</style>
"""


# ============================================================================
# DEBUG / TESTING
# ============================================================================

if __name__ == '__main__':
    print("SADDL AdPulse Design System")
    print("=" * 40)
    print(f"\nPrimary Color: {COLORS['primary']}")
    print(f"Background: {COLORS['background']}")
    print(f"Font Family: {TYPOGRAPHY['font_family'][:50]}...")
    print(f"Base Spacing: {SPACING['md']}")
    print(f"Border Radius: {GLASSMORPHIC['border_radius']}")
