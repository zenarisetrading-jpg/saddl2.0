# 🎨 **Design Consistency Guidelines - Glassmorphic Onboarding**

## 📋 **Design System Extraction**

### **Instructions for Claude:**

**BEFORE implementing any UI components, you must first audit and document the existing design system:**

**1. Extract Color Palette**

Scan these files for color definitions:
- Main dashboard/home page
- Settings pages
- Any CSS/style files
- Streamlit custom themes

Document:
- Primary brand color (likely blue)
- Secondary/accent colors
- Background colors (dark/light modes if applicable)
- Text colors (primary, secondary, muted)
- Success/error/warning/info colors
- Border/divider colors
- Glassmorphic overlay colors (typically rgba with low opacity)

**Create a centralized style configuration:**

```python
# config/design_system.py

COLORS = {
    'primary': '#2563eb',  # Extract from existing app
    'primary_dark': '#1e40af',
    'secondary': '#64748b',
    'accent': '#3b82f6',
    
    'background': '#0f172a',  # Extract actual values
    'background_light': '#1e293b',
    'surface': 'rgba(255, 255, 255, 0.05)',  # Glassmorphic
    'surface_hover': 'rgba(255, 255, 255, 0.1)',
    
    'text_primary': '#f1f5f9',
    'text_secondary': '#cbd5e1',
    'text_muted': '#64748b',
    
    'border': 'rgba(255, 255, 255, 0.1)',
    'border_focus': 'rgba(37, 99, 235, 0.5)',
    
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
    'info': '#3b82f6',
}

TYPOGRAPHY = {
    'font_family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    'heading_xl': '48px',
    'heading_lg': '36px',
    'heading_md': '28px',
    'heading_sm': '20px',
    'body_lg': '18px',
    'body_md': '16px',
    'body_sm': '14px',
    'caption': '12px',
}

SPACING = {
    'xs': '4px',
    'sm': '8px',
    'md': '16px',
    'lg': '24px',
    'xl': '32px',
    'xxl': '48px',
    'xxxl': '64px',
}

GLASSMORPHIC = {
    'backdrop_filter': 'blur(16px) saturate(180%)',
    'background': 'rgba(255, 255, 255, 0.05)',
    'border': '1px solid rgba(255, 255, 255, 0.1)',
    'border_radius': '16px',
    'box_shadow': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
}
```

**Guardrail:** Do NOT make up colors. Extract actual hex/rgba values from existing pages.

---

## 🎭 **SVG Icon System**

### **Instructions for Claude:**

**2.1 Create Glassmorphic SVG Icon Component**

**DO NOT use:**
- Emoji (👋, 🚀, 📊, etc.)
- Unicode symbols
- Font Awesome or other icon fonts
- PNG/JPG images
- Generic Material Icons

**DO create:**
- Custom SVG icons with glassmorphic styling
- Consistent stroke width (2px typically)
- Rounded line caps
- Subtle gradients where appropriate

**Create a reusable icon component:**

```python
# components/icons.py

def glassmorphic_icon(icon_name: str, size: int = 64, color: str = None) -> str:
    """
    Returns SVG string for glassmorphic icon
    
    Args:
        icon_name: Name of icon (welcome, dashboard, impact, optimizer, etc.)
        size: Icon size in pixels
        color: Optional color override (defaults to primary)
    """
    
    if color is None:
        color = COLORS['primary']
    
    icons = {
        'welcome': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="30" fill="{GLASSMORPHIC['background']}" 
                        stroke="url(#grad1)" stroke-width="2"/>
                <path d="M20 28 Q32 20 44 28" stroke="url(#grad1)" stroke-width="2.5" 
                      stroke-linecap="round" fill="none"/>
                <circle cx="24" cy="32" r="2" fill="url(#grad1)"/>
                <circle cx="40" cy="32" r="2" fill="url(#grad1)"/>
                <path d="M22 40 Q32 46 42 40" stroke="url(#grad1)" stroke-width="2.5" 
                      stroke-linecap="round" fill="none"/>
            </svg>
        ''',
        
        'dashboard': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad2" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <rect x="12" y="12" width="18" height="18" rx="4" 
                      fill="{GLASSMORPHIC['background']}" stroke="url(#grad2)" stroke-width="2"/>
                <rect x="34" y="12" width="18" height="18" rx="4" 
                      fill="{GLASSMORPHIC['background']}" stroke="url(#grad2)" stroke-width="2"/>
                <rect x="12" y="34" width="18" height="18" rx="4" 
                      fill="{GLASSMORPHIC['background']}" stroke="url(#grad2)" stroke-width="2"/>
                <rect x="34" y="34" width="18" height="18" rx="4" 
                      fill="{GLASSMORPHIC['background']}" stroke="url(#grad2)" stroke-width="2"/>
            </svg>
        ''',
        
        'impact': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad3" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <path d="M12 48 L22 38 L32 42 L42 28 L52 32" 
                      stroke="url(#grad3)" stroke-width="3" stroke-linecap="round" 
                      stroke-linejoin="round" fill="none"/>
                <circle cx="22" cy="38" r="3" fill="url(#grad3)"/>
                <circle cx="32" cy="42" r="3" fill="url(#grad3)"/>
                <circle cx="42" cy="28" r="3" fill="url(#grad3)"/>
                <circle cx="52" cy="32" r="3" fill="url(#grad3)"/>
            </svg>
        ''',
        
        'optimizer': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad4" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="20" fill="{GLASSMORPHIC['background']}" 
                        stroke="url(#grad4)" stroke-width="2"/>
                <path d="M32 12 L32 24" stroke="url(#grad4)" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M32 40 L32 52" stroke="url(#grad4)" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M12 32 L24 32" stroke="url(#grad4)" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M40 32 L52 32" stroke="url(#grad4)" stroke-width="2.5" stroke-linecap="round"/>
                <circle cx="32" cy="32" r="6" fill="url(#grad4)"/>
            </svg>
        ''',
        
        'connect': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad5" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="20" cy="20" r="8" fill="{GLASSMORPHIC['background']}" 
                        stroke="url(#grad5)" stroke-width="2"/>
                <circle cx="44" cy="44" r="8" fill="{GLASSMORPHIC['background']}" 
                        stroke="url(#grad5)" stroke-width="2"/>
                <path d="M26 26 L38 38" stroke="url(#grad5)" stroke-width="2.5" 
                      stroke-linecap="round" stroke-dasharray="4 4"/>
            </svg>
        ''',
        
        'email': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad6" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <rect x="12" y="18" width="40" height="28" rx="4" 
                      fill="{GLASSMORPHIC['background']}" stroke="url(#grad6)" stroke-width="2"/>
                <path d="M12 22 L32 34 L52 22" stroke="url(#grad6)" stroke-width="2.5" 
                      stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',
        
        'checkmark': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad7" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{COLORS['success']};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{color};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="28" fill="{GLASSMORPHIC['background']}" 
                        stroke="url(#grad7)" stroke-width="2"/>
                <path d="M20 32 L28 40 L44 24" stroke="url(#grad7)" stroke-width="3" 
                      stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
        ''',
        
        'warning': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad8" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{COLORS['warning']};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['error']};stop-opacity:0.6" />
                    </linearGradient>
                </defs>
                <path d="M32 12 L52 48 L12 48 Z" fill="{GLASSMORPHIC['background']}" 
                      stroke="url(#grad8)" stroke-width="2" stroke-linejoin="round"/>
                <path d="M32 24 L32 34" stroke="url(#grad8)" stroke-width="3" stroke-linecap="round"/>
                <circle cx="32" cy="42" r="2" fill="url(#grad8)"/>
            </svg>
        ''',
        
        'loading': f'''
            <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none">
                <defs>
                    <linearGradient id="grad9" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:{COLORS['accent']};stop-opacity:0" />
                    </linearGradient>
                </defs>
                <circle cx="32" cy="32" r="28" stroke="url(#grad9)" stroke-width="4" 
                        stroke-linecap="round" fill="none"
                        stroke-dasharray="140 40">
                    <animateTransform attributeName="transform" type="rotate"
                        from="0 32 32" to="360 32 32" dur="1.5s" repeatCount="indefinite"/>
                </circle>
            </svg>
        ''',
    }
    
    return icons.get(icon_name, icons['welcome'])
```

**Guardrail:** Test each icon at different sizes (32px, 64px, 128px) to ensure clarity.

---

## 🧩 **Reusable Styled Components**

### **Instructions for Claude:**

**3.1 Create Glassmorphic Component Library**

Build reusable components that match the existing app aesthetic:

```python
# components/glassmorphic_ui.py

from config.design_system import COLORS, GLASSMORPHIC, TYPOGRAPHY, SPACING

def glassmorphic_card(content: str, padding: str = SPACING['lg']) -> str:
    """Glassmorphic container matching app style"""
    return f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {padding};
            box-shadow: {GLASSMORPHIC['box_shadow']};
        ">
            {content}
        </div>
    '''

def glassmorphic_button(
    text: str, 
    button_type: str = 'primary',
    full_width: bool = False
) -> str:
    """Styled button matching app design"""
    
    styles = {
        'primary': {
            'background': f'linear-gradient(135deg, {COLORS["primary"]}, {COLORS["accent"]})',
            'color': COLORS['text_primary'],
            'border': 'none',
        },
        'secondary': {
            'background': GLASSMORPHIC['background'],
            'color': COLORS['text_primary'],
            'border': GLASSMORPHIC['border'],
        },
        'ghost': {
            'background': 'transparent',
            'color': COLORS['text_secondary'],
            'border': f'1px solid {COLORS["border"]}',
        }
    }
    
    style = styles.get(button_type, styles['primary'])
    width = '100%' if full_width else 'auto'
    
    return f'''
        <button style="
            background: {style['background']};
            color: {style['color']};
            border: {style['border']};
            border-radius: 12px;
            padding: 14px 32px;
            font-size: {TYPOGRAPHY['body_md']};
            font-weight: 600;
            cursor: pointer;
            width: {width};
            transition: all 0.3s ease;
            backdrop-filter: blur(8px);
        " onmouseover="
            this.style.transform='translateY(-2px)';
            this.style.boxShadow='0 8px 24px rgba(37, 99, 235, 0.3)';
        " onmouseout="
            this.style.transform='translateY(0)';
            this.style.boxShadow='none';
        ">
            {text}
        </button>
    '''

def progress_indicator(current_step: int, total_steps: int) -> str:
    """Glassmorphic progress bar"""
    progress_percent = (current_step / total_steps) * 100
    
    return f'''
        <div style="
            width: 100%;
            height: 4px;
            background: {GLASSMORPHIC['background']};
            border-radius: 2px;
            overflow: hidden;
            margin: {SPACING['lg']} 0;
        ">
            <div style="
                width: {progress_percent}%;
                height: 100%;
                background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['accent']});
                transition: width 0.3s ease;
                box-shadow: 0 0 12px {COLORS['primary']};
            "></div>
        </div>
        <div style="
            text-align: center;
            color: {COLORS['text_muted']};
            font-size: {TYPOGRAPHY['body_sm']};
            margin-top: {SPACING['sm']};
        ">
            Step {current_step} of {total_steps}
        </div>
    '''

def value_prop_card(icon_name: str, title: str, description: str) -> str:
    """Value proposition card with icon"""
    from components.icons import glassmorphic_icon
    
    icon_svg = glassmorphic_icon(icon_name, size=48)
    
    return f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {SPACING['xl']};
            text-align: center;
            transition: all 0.3s ease;
            height: 100%;
        " onmouseover="
            this.style.transform='translateY(-4px)';
            this.style.borderColor='rgba(37, 99, 235, 0.3)';
        " onmouseout="
            this.style.transform='translateY(0)';
            this.style.borderColor='rgba(255, 255, 255, 0.1)';
        ">
            <div style="margin-bottom: {SPACING['md']};">
                {icon_svg}
            </div>
            <h3 style="
                color: {COLORS['text_primary']};
                font-size: {TYPOGRAPHY['heading_sm']};
                font-weight: 600;
                margin-bottom: {SPACING['sm']};
            ">
                {title}
            </h3>
            <p style="
                color: {COLORS['text_secondary']};
                font-size: {TYPOGRAPHY['body_md']};
                line-height: 1.6;
            ">
                {description}
            </p>
        </div>
    '''

def info_banner(message: str, banner_type: str = 'info') -> str:
    """Styled banner for notifications"""
    
    colors = {
        'info': COLORS['info'],
        'success': COLORS['success'],
        'warning': COLORS['warning'],
        'error': COLORS['error'],
    }
    
    color = colors.get(banner_type, colors['info'])
    
    return f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: {SPACING['md']} {SPACING['lg']};
            margin: {SPACING['md']} 0;
            color: {COLORS['text_primary']};
            font-size: {TYPOGRAPHY['body_md']};
        ">
            {message}
        </div>
    '''
```

**Guardrail:** Before creating these components, inspect existing components in the app and match their exact styling patterns.

---

## 📄 **Updated Page Implementations**

### **Instructions for Claude:**

**4. Rework All Onboarding Pages to Use Design System**

**For each page created in the original plan, apply these modifications:**

**4.1 Invitation Acceptance Page - Styled Version**

Instead of plain Streamlit components, use:

```python
# pages/accept_invite.py

import streamlit as st
from components.glassmorphic_ui import *
from components.icons import glassmorphic_icon
from config.design_system import COLORS, TYPOGRAPHY, SPACING

st.set_page_config(
    page_title="Accept Invitation - SADDL AdPulse",
    page_icon="📧",
    layout="centered"
)

# Apply dark theme to match app
st.markdown(f"""
<style>
    .stApp {{
        background: {COLORS['background']};
        color: {COLORS['text_primary']};
    }}
    
    /* Match existing app's input styling */
    input, .stTextInput input {{
        background: {GLASSMORPHIC['background']} !important;
        backdrop-filter: {GLASSMORPHIC['backdrop_filter']} !important;
        border: {GLASSMORPHIC['border']} !important;
        border-radius: 12px !important;
        color: {COLORS['text_primary']} !important;
        padding: 12px 16px !important;
        font-size: {TYPOGRAPHY['body_md']} !important;
    }}
    
    input:focus {{
        border-color: {COLORS['border_focus']} !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
    }}
    
    /* Match button styling */
    .stButton button {{
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['accent']}) !important;
        color: {COLORS['text_primary']} !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 32px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }}
    
    .stButton button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.3);
    }}
    
    /* Match checkbox styling */
    .stCheckbox {{
        color: {COLORS['text_primary']} !important;
    }}
</style>
""", unsafe_allow_html=True)

# Header with glassmorphic icon
st.markdown(f"""
<div style="text-align: center; padding: {SPACING['xxxl']} 0 {SPACING['xl']} 0;">
    <div style="margin-bottom: {SPACING['lg']};">
        {glassmorphic_icon('welcome', size=80)}
    </div>
    <h1 style="
        color: {COLORS['text_primary']};
        font-size: {TYPOGRAPHY['heading_xl']};
        margin-bottom: {SPACING['sm']};
        font-weight: 700;
    ">
        SADDL AdPulse
    </h1>
    <p style="
        font-size: {TYPOGRAPHY['body_lg']};
        color: {COLORS['text_secondary']};
    ">
        Decision-First PPC Platform
    </p>
</div>
""", unsafe_allow_html=True)

# Rest of page continues with consistent styling...
```

**4.2 Onboarding Wizard - Styled Version**

Apply same principle to each onboarding step:

```python
# Step 1: Welcome
if st.session_state.onboarding_step == 1:
    # Progress indicator using design system
    st.markdown(progress_indicator(1, 3), unsafe_allow_html=True)
    
    # Hero section with glassmorphic styling
    st.markdown(f"""
    <div style="text-align: center; padding: {SPACING['xxxl']} 0;">
        <div style="margin-bottom: {SPACING['lg']};">
            {glassmorphic_icon('welcome', size=96)}
        </div>
        <h1 style="
            font-size: {TYPOGRAPHY['heading_xl']};
            color: {COLORS['text_primary']};
            margin-bottom: {SPACING['md']};
            font-weight: 700;
        ">
            Welcome to SADDL AdPulse
        </h1>
        <p style="
            font-size: {TYPOGRAPHY['body_lg']};
            color: {COLORS['text_secondary']};
            max-width: 800px;
            margin: 0 auto;
            line-height: 1.6;
        ">
            The only PPC platform that shows you the <strong style="color: {COLORS['primary']};">actual impact</strong> of every optimization decision.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Value props in glassmorphic cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            value_prop_card(
                'impact',
                'Decision-First',
                'See which actions actually moved the needle vs. which were noise'
            ),
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            value_prop_card(
                'dashboard',
                'Transparent Attribution',
                'White-box measurement you can verify and trust'
            ),
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            value_prop_card(
                'optimizer',
                'Proven ROI',
                'Built by a 7-figure seller who needed better PPC tools'
            ),
            unsafe_allow_html=True
        )
```

**4.3 Empty State - Implemented Version (See: `ui/components/empty_states.py`)**

The empty state system has been centralized into `render_empty_state(state_type, **kwargs)`.

**Supported States:**
1.  **`no_account`**: Welcome screen with "Connect Account" CTA.
    *   *Usage*: New user onboarding.
2.  **`no_data`**: "Setting up data" screen with refresh button.
    *   *Usage*: Account connected but data ingestion pending.
3.  **`filtered_empty`**: "No results found" for active filters.
    *   *Usage*: Dashboard when filter criteria yield 0 rows.

**Usage Example:**
```python
from ui.components.empty_states import render_empty_state

# Welcome Screen
render_empty_state("no_account")

# Syncing Screen
render_empty_state("no_data", account_name="My Brand")

# Filter Empty
render_empty_state("filtered_empty", message="Try adjusting your date range.")
```

---

## 🎨 **Specific Styling Adjustments**

### **Instructions for Claude:**

**5. Match These Exact Elements from Main App**

**5.1 Extract and Match Navigation/Header Style**

Look at the main app's header/navigation:
- Background color/gradient
- Logo treatment
- Navigation link styling
- User menu styling

Apply same styling to onboarding pages.

**5.2 Extract and Match Form Input Styles**

Inspect existing forms in Settings:
- Input field background
- Border style and color
- Focus state
- Placeholder text color
- Label positioning and color

**5.3 Extract and Match Table/Card Styles**

Look at Decision Cockpit and other data pages:
- Card container styling
- Border radius values
- Shadow depths
- Hover effects
- Spacing between elements

**5.4 Extract and Match Typography**

Check all headings and body text:
- Font family
- Font weights used (400, 500, 600, 700)
- Line heights
- Letter spacing
- Text colors for different hierarchy levels

**5.5 Extract and Match Animation Patterns**

Note any animations/transitions in the app:
- Button hover effects
- Page transitions
- Loading states
- Micro-interactions

Apply same timing and easing functions.

---

## ✅ **Style Consistency Checklist**

### **Before Deploying Each Component:**

**Visual Audit:**
- [ ] Place new component screenshot next to main app screenshot
- [ ] Colors match exactly (use color picker to verify)
- [ ] Border radius values are consistent
- [ ] Spacing follows same scale (4px, 8px, 16px, 24px, etc.)
- [ ] Font sizes match hierarchy
- [ ] Icons use same stroke width and style
- [ ] Glassmorphic effects have same blur/opacity values
- [ ] Shadows match depth and color
- [ ] Hover states feel consistent
- [ ] Transitions have same duration/easing

**Functional Audit:**
- [ ] Forms validate the same way
- [ ] Error messages use same styling
- [ ] Success states look identical
- [ ] Loading indicators match
- [ ] Empty states follow same pattern
- [ ] Tooltips appear consistently
- [ ] Modals/dialogs use same styling

**Accessibility Audit:**
- [ ] Color contrast ratios maintained
- [ ] Focus states clearly visible
- [ ] Keyboard navigation works
- [ ] Screen reader compatibility
- [ ] Touch target sizes appropriate

---

## 🔧 **Implementation Strategy**

**Phase-by-Phase Styling:**

**Phase 1: Foundation**
1. Extract design system from main app
2. Create `config/design_system.py`
3. Create `components/icons.py` with all needed SVG icons
4. Create `components/glassmorphic_ui.py` with reusable components
5. Test components in isolation

**Phase 2: Apply to Team Settings**
1. Update invitation form to use new components
2. Test that it visually matches existing settings pages
3. Verify functionality unchanged

**Phase 3: Build Acceptance Page**
1. Use design system components throughout
2. Match existing login/auth page styling exactly
3. Test side-by-side with main app

**Phase 4: Build Onboarding Wizard**
1. Each step uses design system
2. Transitions match app's navigation patterns
3. Icons and illustrations consistent

**Phase 5: Update Empty States**
1. Replace plain text with styled components
2. Add appropriate glassmorphic icons
3. Ensure CTAs match button styling throughout app

**Guardrails:**
- Never mix styling approaches (no emojis + glassmorphic icons together)
- Always use design system variables, not hard-coded values
- Test on multiple screen sizes
- Verify dark mode consistency (if applicable)
- Get visual approval before moving to next phase

---

## 🎯 **Final Validation**

**Before considering implementation complete:**

1. **Screenshot Test:** Take 10 screenshots mixing main app and onboarding pages. Should be impossible to tell which is which.

2. **User Test:** Show to someone unfamiliar with the app. Ask: "Does this feel like one cohesive product?" Should be yes.

3. **Brand Test:** Does onboarding reinforce the premium, professional, "built by experts" positioning? Should feel enterprise-grade.

4. **Consistency Test:** Open 5 random pages in the app. New pages should feel native, not "tacked on."

**Success Criteria:**
- Zero visual disconnect between onboarding and main app
- All icons are custom SVG with glassmorphic treatment
- Color palette extracted and applied perfectly
- Typography hierarchy matches exactly
- Spacing and layout patterns consistent
- Animations/transitions feel cohesive
- Overall experience feels premium and polished

---

**Claude should treat this as a HARD REQUIREMENT:** The onboarding experience must be visually indistinguishable from the main application. No emojis, no generic icons, no inconsistent styling. This is a premium product with premium design - the onboarding should reflect that from the first interaction.
