  # SADDLE – Brand Color Palette & Usage Guidelines

  ## 1. Core Brand Colors (Primary)

  ### Saddle Deep Purple (Primary Base)
  - **Hex:** `#5B5670`
  - **RGB:** 91, 86, 112
  - **Usage:** App background (dark sections), header/hero panels, primary containers
  - **Meaning:** Calm authority, technical depth, trust

  ### Charcoal Black (Anchor / Contrast)
  - **Hex:** `#0B0B0D`
  - **RGB:** 11, 11, 13
  - **Usage:** Footer bars, login base strip, text on light backgrounds
  - **Meaning:** Serious, grounded, enterprise-grade

  ### Soft White (Primary Text / Logo Type)
  - **Hex:** `#E9EAF0`
  - **RGB:** 233, 234, 240
  - **Usage:** Logo wordmark, primary text on dark backgrounds
  - **Meaning:** Clarity, restraint, premium feel

  ---

  ## 2. Accent Colors (Decision & Signal)

  ### Signal Blue (Decision Accent)
  - **Hex:** `#2A8EC9`
  - **RGB:** 42, 142, 201
  - **Usage:** Key data points, incremental bars, "Validated / Confirmed" states
  - **Rule:** Use only where decisions or validation are shown

  ### Muted Cyan (Secondary Signal)
  - **Hex:** `#8FC9D6`
  - **RGB:** 143, 201, 214
  - **Usage:** Secondary indicators, supporting dots/connectors
  - **Rule:** Never use alone — always paired with Signal Blue

  ---

  ## 3. Neutral Support Palette

  | Color | Hex | Usage |
  |-------|-----|-------|
  | Slate Grey | `#9A9AAA` | Subtext, axis labels, secondary UI copy |
  | Light Grey | `#D6D7DE` | Dividers, disabled states, inactive icons |

  ---

  ## 4. Logo Usage Rules

  ### ✅ Allowed
  - Logo on solid dark backgrounds only
  - Wordmark in Soft White
  - Icon dots in Signal Blue / Muted Cyan only

  ### ❌ Not Allowed
  - Gradients inside the logo
  - Shadow effects
  - Changing dot colors
  - Using logo on busy charts or images
  - Placing logo on pure white without a container

  ---

  ## 5. UI Color Hierarchy

  | Purpose | Color |
  |---------|-------|
  | Primary action / insight | Signal Blue `#2A8EC9` |
  | Neutral data | Soft White / Slate Grey |
  | Background | Saddle Deep Purple `#5B5670` |
  | Warnings / negatives | Desaturated greys only (no red) |

  > **Note:** No red or green by default. This reinforces "evidence-first, not emotional" positioning.

  ---

  ## 6. Typography

  - **Headlines:** Inter / Satoshi / SF Pro (SemiBold)
  - **Body:** Inter / SF Pro (Regular)
  - **Numbers:** Same family, tabular numerals enabled

  > No decorative fonts. No rounded playful typefaces.

  ---

  ## 7. Brand Personality

  - ❌ Not flashy AI
  - ❌ Not growth-hack SaaS
  - ✅ Calm, confident, operator-built
  - ✅ Trust before automation
  - ✅ Decisions over dashboards

  ---

  ## Quick Reference (CSS Variables)

  ```css
  :root {
    /* Core */
    --saddle-purple: #5B5670;
    --saddle-black: #0B0B0D;
    --saddle-white: #E9EAF0;
    
    /* Accent */
    --signal-blue: #2A8EC9;
    --muted-cyan: #8FC9D6;
    
    /* Neutral */
    --slate-grey: #9A9AAA;
    --light-grey: #D6D7DE;
  }
  ```

  ---

  ## 8. Light Theme Specification

  > "A calm audit room, not a SaaS landing page"

  ### Global Backgrounds
  | Element | Color | Note |
  |---------|-------|------|
  | App background | `#F3F4F7` | Soft cool grey (NOT pure white) |
  | Sidebar | `#E8EAF0` | Slightly darker |
  | Cards | `#FFFFFF` | White allowed only inside cards |

  ### Typography
  | Type | Color | Usage |
  |------|-------|-------|
  | Primary | `#1F2430` | Headings, key metrics, labels |
  | Secondary | `#5E6475` | Descriptions, helper copy |
  | Muted | `#9A9AAA` | Disabled text |

  ### Tables
  | Element | Color |
  |---------|-------|
  | Background | `#FFFFFF` |
  | Header row | `#F7F8FB` |
  | Row divider | `#ECEEF4` |
  | Hover state | `#F1F4FA` |
  | Selected row | `#EAF3FB` |

  ### Cards & Borders
  - **Card background:** `#FFFFFF`
  - **Border:** `1px solid #E2E4EC`
  - **Shadow:** `0 1px 2px rgba(0,0,0,0.04)` (very subtle)

  ### CTAs
  | Type | Style |
  |------|-------|
  | Primary | Background `#2A8EC9`, Text `#FFFFFF` |
  | Secondary | Border `#2A8EC9`, Text `#2A8EC9`, Transparent bg |
  | Tertiary | Text only `#5E6475` |

  > ⚠️ One primary CTA per screen. No competing buttons.

  ### Charts
  - **Axis lines:** `#E6E8F0`
  - **Labels:** `#5E6475`
  - **Canvas:** Transparent (inherits card white)

---

## 9. Premium Dashboard UI (Dark Mode)

> Applied to: Executive Dashboard, Decision Cockpit, What-If Forecast

### Dark Theme Colors
| Name | Hex | Usage |
|------|-----|-------|
| **Cyan Primary** | `#06B6D4` | Accents, icons, borders, highlights |
| **Cyan Light** | `#22D3EE` | Active states, important values |
| **Dark Base** | `#0F172A` | Primary background |
| **Dark Secondary** | `#1E293B` | Cards, elevated surfaces |
| **Primary Text** | `#F8FAFC` | Headers, key metrics |
| **Secondary Text** | `#94A3B8` | Body text, labels |
| **Muted Text** | `#64748B` | Captions, metadata |

### Status Colors (with Glow)
| Status | Color | Glow Effect |
|--------|-------|-------------|
| Success | `#10B981` | `text-shadow: 0 0 20px rgba(16, 185, 129, 0.5)` |
| Warning | `#F59E0B` | `text-shadow: 0 0 20px rgba(245, 158, 11, 0.5)` |
| Danger | `#EF4444` | `text-shadow: 0 0 20px rgba(239, 68, 68, 0.5)` |

### Glassmorphic Card
```css
background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
backdrop-filter: blur(10px);
border: 1px solid rgba(148, 163, 184, 0.15);
border-radius: 16px;
padding: 16px;
box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
```

### Section Header
```css
display: flex;
align-items: center;
gap: 12px;
background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
border-left: 3px solid #06B6D4;
border-radius: 8px;
padding: 12px 16px;
```

### Risk Cards (Colored Gradients)
```css
/* High Risk */
background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(15, 23, 42, 0.9) 100%);
border: 1px solid rgba(239, 68, 68, 0.3);

/* Medium Risk */
background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(15, 23, 42, 0.9) 100%);
border: 1px solid rgba(245, 158, 11, 0.3);

/* Low Risk */
background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(15, 23, 42, 0.9) 100%);
border: 1px solid rgba(16, 185, 129, 0.3);
```

### Chart Styling (Plotly)
```python
fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(
        gridcolor='rgba(6, 182, 212, 0.1)',
        tickfont=dict(color='#94A3B8'),
        title=dict(font=dict(color='#F8FAFC'))
    )
)
# Primary trace: #06B6D4, Fill: rgba(6, 182, 212, 0.1)
```

### Typography Scale
| Element | Style |
|---------|-------|
| Hero Metric | `3rem / 800 weight` + status color glow |
| Card Value | `1.5rem / 700 weight` |
| Section Header | `1.1rem / 700 weight / 0.02em spacing` |
| Label | `0.75rem / 700 weight / uppercase / 1px spacing` |
| Delta | `0.85rem` + status color |

### Icon Guidelines
- Use **SVG icons** (not emoji) for cross-platform consistency
- Stroke width: `2`
- Colors: `#06B6D4` (cyan), `#64748B` (muted), or status colors
- Size: 16-20px inline, 24px for headers

### Streamlit Implementation Notes
> ⚠️ Streamlit's `st.markdown(unsafe_allow_html=True)` doesn't reliably apply CSS classes. **Always use inline styles.**

```python
card_style = "background: linear-gradient(...); border-radius: 16px; padding: 16px;"
st.markdown(f'<div style="{card_style}">Content</div>', unsafe_allow_html=True)
```

### Design Principles
1. **Dark-First** — All backgrounds dark, content pops with color
2. **Cyan Accent** — Primary brand color for accents only, not backgrounds
3. **Glassmorphic Depth** — Layered gradients with subtle blur
4. **Glowing Status** — Status colors have matching glow/shadow effects
5. **Minimal Borders** — Use gradients and shadows over hard borders
6. **SVG > Emoji** — Vector icons for visual consistency

CRITICAL GUARDRAILS
DO NOT:

❌ Change any calculation logic or forecasting algorithms
❌ Modify data fetching or processing
❌ Alter scenario probability calculations
❌ Touch risk analysis business logic
❌ Break existing functionality

DO:

✅ Add premium CSS styling only
✅ Restructure HTML for visual hierarchy
✅ Enhance chart presentation
✅ Create clear before/after visual separation
✅ Keep all existing features working

✅ VALIDATION REQUIREMENTS
After implementation, verify:

 Page loads without errors
 Risk cards have dramatic styling with glow effects
 Tables have premium styling and hover states

 Section headers have glassmorphic backgrounds
 All animations work smoothly
 Existing functionality unchanged (scenarios calculate correctly)
 No calculation logic was modified
 Mobile responsive
