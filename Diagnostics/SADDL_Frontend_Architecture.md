# SADDL AdPulse — Frontend Architecture
## Glassmorphic Design System & Diagnostic Dashboard

**Version:** 1.0  
**Date:** February 2026  
**Stack:** Streamlit 1.32+, Custom CSS, SVG Icons

---

## 1. Design System

### 1.1 Color Palette

**Primary Colors:**
```css
:root {
  /* Brand */
  --primary-600: #2563eb;      /* Primary blue */
  --primary-500: #3b82f6;
  --primary-400: #60a5fa;
  
  /* Accent */
  --accent-600: #7c3aed;       /* Purple accent */
  --accent-500: #8b5cf6;
  --accent-400: #a78bfa;
  
  /* Semantic */
  --success-600: #059669;
  --success-500: #10b981;
  --success-400: #34d399;
  
  --warning-600: #d97706;
  --warning-500: #f59e0b;
  --warning-400: #fbbf24;
  
  --error-600: #dc2626;
  --error-500: #ef4444;
  --error-400: #f87171;
  
  /* Neutrals (Dark Theme Base) */
  --gray-950: #030712;         /* App background */
  --gray-900: #111827;         /* Card background base */
  --gray-800: #1f2937;
  --gray-700: #374151;
  --gray-600: #4b5563;
  --gray-500: #6b7280;
  --gray-400: #9ca3af;
  --gray-300: #d1d5db;
  --gray-200: #e5e7eb;
  --gray-100: #f3f4f6;
  
  /* Glassmorphic overlays */
  --glass-white: rgba(255, 255, 255, 0.05);
  --glass-white-strong: rgba(255, 255, 255, 0.1);
  --glass-dark: rgba(0, 0, 0, 0.2);
  --glass-gradient: linear-gradient(135deg, 
                      rgba(255, 255, 255, 0.1) 0%, 
                      rgba(255, 255, 255, 0.05) 100%);
}
```

**Usage Guidelines:**
- Background: `--gray-950` for app, `--gray-900` for cards
- Text: `--gray-100` for primary, `--gray-400` for secondary
- Interactive: `--primary-500` for buttons, `--accent-500` for highlights
- Status indicators:
  - Critical/High: `--error-500`
  - Warning/Medium: `--warning-500`
  - Success/Low: `--success-500`
  - Neutral: `--gray-500`

---

### 1.2 Typography

**Font Stack:**
```css
:root {
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}
```

**Type Scale:**
```css
:root {
  /* Headings */
  --text-5xl: 3rem;      /* 48px - Page titles */
  --text-4xl: 2.25rem;   /* 36px - Section headers */
  --text-3xl: 1.875rem;  /* 30px - Card titles */
  --text-2xl: 1.5rem;    /* 24px - Subheadings */
  --text-xl: 1.25rem;    /* 20px - Card headers */
  --text-lg: 1.125rem;   /* 18px - Large body */
  
  /* Body */
  --text-base: 1rem;     /* 16px - Default */
  --text-sm: 0.875rem;   /* 14px - Secondary */
  --text-xs: 0.75rem;    /* 12px - Captions */
  
  /* Weights */
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;
  
  /* Line heights */
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;
}
```

**Typography Classes:**
```css
.heading-page {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  line-height: var(--leading-tight);
  color: var(--gray-100);
  letter-spacing: -0.02em;
}

.heading-section {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  line-height: var(--leading-tight);
  color: var(--gray-100);
}

.text-body {
  font-size: var(--text-base);
  font-weight: var(--font-normal);
  line-height: var(--leading-normal);
  color: var(--gray-300);
}

.text-secondary {
  font-size: var(--text-sm);
  font-weight: var(--font-normal);
  color: var(--gray-400);
}

.text-caption {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--gray-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

---

### 1.3 Glassmorphism Specifications

**Core Glass Effect:**
```css
.glass-card {
  background: linear-gradient(135deg, 
                rgba(255, 255, 255, 0.1) 0%, 
                rgba(255, 255, 255, 0.05) 100%);
  backdrop-filter: blur(10px) saturate(180%);
  -webkit-backdrop-filter: blur(10px) saturate(180%);
  
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.3),
    0 2px 4px -1px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
}

.glass-card-strong {
  background: linear-gradient(135deg, 
                rgba(255, 255, 255, 0.15) 0%, 
                rgba(255, 255, 255, 0.08) 100%);
  backdrop-filter: blur(16px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.glass-card-subtle {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.05);
}
```

**Interactive Glass States:**
```css
.glass-card:hover {
  background: linear-gradient(135deg, 
                rgba(255, 255, 255, 0.12) 0%, 
                rgba(255, 255, 255, 0.06) 100%);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-2px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-card:active {
  transform: translateY(0);
  box-shadow: 
    0 2px 4px -1px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
}
```

**Gradient Overlays:**
```css
.gradient-accent {
  background: linear-gradient(135deg, 
                var(--primary-500) 0%, 
                var(--accent-500) 100%);
}

.gradient-success {
  background: linear-gradient(135deg, 
                var(--success-500) 0%, 
                var(--primary-500) 100%);
}

.gradient-warning {
  background: linear-gradient(135deg, 
                var(--warning-500) 0%, 
                var(--error-500) 100%);
}
```

---

### 1.4 Spacing System

**Base Unit:** 4px (0.25rem)

```css
:root {
  --space-0: 0;
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
  --space-20: 5rem;     /* 80px */
}
```

**Layout Grid:**
```css
.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-6);
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-6);
}

.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
```

---

## 2. SVG Icon Library

**Icon Specifications:**
- Size: 24×24px default (scale with CSS)
- Stroke width: 2px
- Corner radius: 2px
- Style: Outline (not filled)
- Color: Inherit from parent

### 2.1 Status Icons

**Success (Checkmark Circle):**
```html
<svg class="icon icon-success" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
  <path d="M8 12L11 15L16 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Warning (Alert Triangle):**
```html
<svg class="icon icon-warning" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 2L2 20H22L12 2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
  <path d="M12 9V13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <circle cx="12" cy="17" r="0.5" fill="currentColor"/>
</svg>
```

**Error (X Circle):**
```html
<svg class="icon icon-error" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
  <path d="M15 9L9 15M9 9L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
</svg>
```

**Info (Info Circle):**
```html
<svg class="icon icon-info" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
  <path d="M12 16V12M12 8H12.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
</svg>
```

---

### 2.2 Metric Icons

**Trending Up:**
```html
<svg class="icon icon-trend-up" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M23 6L13.5 15.5L8.5 10.5L1 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M17 6H23V12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Trending Down:**
```html
<svg class="icon icon-trend-down" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M23 18L13.5 8.5L8.5 13.5L1 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M17 18H23V12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Trending Neutral:**
```html
<svg class="icon icon-trend-neutral" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M1 12H23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <path d="M18 7L23 12L18 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Dollar:**
```html
<svg class="icon icon-dollar" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 1V23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <path d="M17 5H9.5C8.57174 5 7.6815 5.36875 7.02513 6.02513C6.36875 6.6815 6 7.57174 6 8.5C6 9.42826 6.36875 10.3185 7.02513 10.9749C7.6815 11.6313 8.57174 12 9.5 12H14.5C15.4283 12 16.3185 12.3687 16.9749 13.0251C17.6313 13.6815 18 14.5717 18 15.5C18 16.4283 17.6313 17.3185 16.9749 17.9749C16.3185 18.6313 15.4283 19 14.5 19H6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Percentage:**
```html
<svg class="icon icon-percent" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <line x1="19" y1="5" x2="5" y2="19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <circle cx="7" cy="7" r="2" stroke="currentColor" stroke-width="2"/>
  <circle cx="17" cy="17" r="2" stroke="currentColor" stroke-width="2"/>
</svg>
```

---

### 2.3 Action Icons

**Eye (View):**
```html
<svg class="icon icon-eye" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M1 12C1 12 5 4 12 4C19 4 23 12 23 12C23 12 19 20 12 20C5 20 1 12 1 12Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
  <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
</svg>
```

**Download:**
```html
<svg class="icon icon-download" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M7 10L12 15L17 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Filter:**
```html
<svg class="icon icon-filter" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M22 3H2L10 12.46V19L14 21V12.46L22 3Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Refresh:**
```html
<svg class="icon icon-refresh" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M23 4V10H17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M1 20V14H7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M3.51 9C4.15839 7.28552 5.25969 5.77735 6.70121 4.62544C8.14274 3.47354 9.8662 2.72111 11.6934 2.44655C13.5207 2.17198 15.3827 2.38477 17.1005 3.0632C18.8183 3.74163 20.3301 4.85967 21.49 6.3L23 10M1 14L2.51 17.7C3.66988 19.1403 5.18167 20.2584 6.89952 20.9368C8.61736 21.6152 10.4793 21.828 12.3066 21.5535C14.1338 21.2789 15.8573 20.5265 17.2988 19.3746C18.7403 18.2227 19.8416 16.7145 20.49 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Dismiss (X):**
```html
<svg class="icon icon-dismiss" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

---

### 2.4 Diagnostic-Specific Icons

**Lightbulb (Opportunity):**
```html
<svg class="icon icon-lightbulb" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M9 18H15M10 22H14M12 2C8.68629 2 6 4.68629 6 8C6 10.5 7 12.5 9 14.5V16C9 16.5523 9.44772 17 10 17H14C14.5523 17 15 16.5523 15 16V14.5C17 12.5 18 10.5 18 8C18 4.68629 15.3137 2 12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Shield (Validation):**
```html
<svg class="icon icon-shield" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 2L4 6V12C4 16.5 7.5 20.5 12 22C16.5 20.5 20 16.5 20 12V6L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M9 12L11 14L15 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Target (Optimization):**
```html
<svg class="icon icon-target" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
  <circle cx="12" cy="12" r="6" stroke="currentColor" stroke-width="2"/>
  <circle cx="12" cy="12" r="2" stroke="currentColor" stroke-width="2"/>
</svg>
```

**Chart Line (Trends):**
```html
<svg class="icon icon-chart-line" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M3 3V21H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M18 9L13 14L9 10L4 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Layers (Account Level):**
```html
<svg class="icon icon-layers" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

**Search (Organic):**
```html
<svg class="icon icon-search" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/>
  <path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
</svg>
```

---

### 2.5 Icon Component (Streamlit)

```python
# components/icon.py
def render_icon(name: str, color: str = None, size: int = 24):
    """
    Render SVG icon with custom color and size.
    
    Args:
        name: Icon name (e.g., 'trend-up', 'warning', 'lightbulb')
        color: CSS color (hex, rgb, or var)
        size: Icon size in pixels
    """
    icons = {
        'trend-up': '<svg viewBox="0 0 24 24" fill="none">...</svg>',
        'trend-down': '<svg viewBox="0 0 24 24" fill="none">...</svg>',
        # ... full library
    }
    
    svg = icons.get(name, icons['info'])
    
    style = f'width: {size}px; height: {size}px;'
    if color:
        style += f' color: {color};'
    
    return f'<span class="icon-wrapper" style="{style}">{svg}</span>'


# Usage in Streamlit
import streamlit as st
from components.icon import render_icon

st.markdown(
    f"""
    <div class="metric-card">
        {render_icon('trend-up', color='var(--success-500)', size=32)}
        <span class="metric-value">+12%</span>
    </div>
    """,
    unsafe_allow_html=True
)
```

---

## 3. Component Library

### 3.1 Metric Card

**Design:**
```
┌────────────────────────────────────────┐
│  [icon]  TACOS                      ↗  │
│          28.2%                         │
│          +2.1pts vs 7d avg             │
└────────────────────────────────────────┘
```

**CSS:**
```css
.metric-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-6);
  
  background: linear-gradient(135deg, 
                rgba(255, 255, 255, 0.1) 0%, 
                rgba(255, 255, 255, 0.05) 100%);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  
  position: relative;
  overflow: hidden;
}

.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, 
                var(--primary-500), 
                var(--accent-500));
  opacity: 0;
  transition: opacity 0.3s;
}

.metric-card:hover::before {
  opacity: 1;
}

.metric-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.metric-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--gray-100);
  line-height: 1;
}

.metric-delta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.metric-delta.positive {
  color: var(--success-400);
}

.metric-delta.negative {
  color: var(--error-400);
}

.metric-delta.neutral {
  color: var(--gray-400);
}
```

**Streamlit Component:**
```python
def metric_card(label: str, value: str, delta: str = None, 
               delta_type: str = 'neutral', icon: str = None):
    """Glassmorphic metric card."""
    
    icon_html = render_icon(icon, size=20) if icon else ''
    
    delta_html = ''
    if delta:
        trend_icon = {
            'positive': 'trend-up',
            'negative': 'trend-down',
            'neutral': 'trend-neutral'
        }.get(delta_type, 'trend-neutral')
        
        delta_html = f"""
        <div class="metric-delta {delta_type}">
            {render_icon(trend_icon, size=16)}
            <span>{delta}</span>
        </div>
        """
    
    return f"""
    <div class="metric-card">
        <div class="metric-header">
            <div class="metric-label">
                {icon_html}
                <span>{label}</span>
            </div>
        </div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """
```

---

### 3.2 Signal Alert Card

**Design:**
```
┌────────────────────────────────────────────────────┐
│  [!] Market Demand Contraction       Confidence 95%│
│      Active for 5 days                              │
├────────────────────────────────────────────────────┤
│  Evidence:                                          │
│    • Organic CVR: -11% (3.2% → 2.8%)               │
│    • Ad CVR: -9% (3.5% → 3.2%)                     │
│    • CPC: +1% (stable)                             │
│                                                     │
│  Impact: -520 AED/day revenue                      │
│                                                     │
│  Diagnosis:                                         │
│  Market-wide conversion decline. Your optimizations│
│  are NOT the primary cause.                        │
│                                                     │
│  Recommended Actions:                               │
│  1. Contract discovery spend 15-20%                │
│  2. Maintain exact match campaigns                 │
│  3. Monitor for 7 days                             │
│                                                     │
│  [View Trend] [Dismiss] [Mark Reviewed]           │
└────────────────────────────────────────────────────┘
```

**CSS:**
```css
.signal-card {
  background: linear-gradient(135deg, 
                rgba(255, 255, 255, 0.08) 0%, 
                rgba(255, 255, 255, 0.04) 100%);
  backdrop-filter: blur(12px);
  border-left: 4px solid var(--signal-color);
  border-radius: 12px;
  padding: var(--space-6);
  margin-bottom: var(--space-4);
}

.signal-card.severity-high {
  --signal-color: var(--error-500);
  border-left-color: var(--error-500);
}

.signal-card.severity-medium {
  --signal-color: var(--warning-500);
  border-left-color: var(--warning-500);
}

.signal-card.severity-low {
  --signal-color: var(--success-500);
  border-left-color: var(--success-500);
}

.signal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.signal-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.signal-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: var(--signal-color);
}

.signal-title h3 {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--gray-100);
  margin: 0;
}

.signal-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--gray-300);
}

.signal-meta {
  font-size: var(--text-sm);
  color: var(--gray-400);
  margin-bottom: var(--space-4);
}

.signal-section {
  margin-bottom: var(--space-4);
}

.signal-section-title {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--gray-300);
  margin-bottom: var(--space-2);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.signal-evidence {
  list-style: none;
  padding: 0;
  margin: 0;
}

.signal-evidence li {
  padding-left: var(--space-4);
  margin-bottom: var(--space-2);
  color: var(--gray-300);
  position: relative;
}

.signal-evidence li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--signal-color);
  font-weight: bold;
}

.signal-impact {
  display: inline-block;
  padding: var(--space-2) var(--space-4);
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
  color: var(--error-400);
  font-weight: var(--font-medium);
}

.signal-diagnosis {
  padding: var(--space-4);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border-left: 2px solid var(--primary-500);
  color: var(--gray-300);
  line-height: var(--leading-relaxed);
}

.signal-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
```

---

### 3.3 Button Styles

**Primary Button:**
```css
.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  text-decoration: none;
  
  border: none;
  border-radius: 8px;
  cursor: pointer;
  
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-primary {
  background: linear-gradient(135deg, 
                var(--primary-500), 
                var(--accent-500));
  color: white;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.4);
}

.btn-primary:active {
  transform: translateY(0);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--gray-300);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
}

.btn-ghost {
  background: transparent;
  color: var(--gray-400);
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--gray-300);
}
```

---

### 3.4 Data Table

**CSS:**
```css
.data-table {
  width: 100%;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table thead {
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.data-table th {
  padding: var(--space-4);
  text-align: left;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.data-table td {
  padding: var(--space-4);
  font-size: var(--text-sm);
  color: var(--gray-300);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table tbody tr {
  transition: background 0.2s;
}

.data-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}
```

---

## 4. Page Wireframes

### 4.1 Overview Page

```
┌──────────────────────────────────────────────────────────────────┐
│  Diagnostics / Overview                      [Download] [Refresh]│
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┬──────────┬──────────┬───────────────────────────┐ │
│  │ [%] TACOS│ [🔍] Org │ [$] Rev  │ [●] Status                │ │
│  │  28.2%   │   58.1%  │ 4,289 AED│  🟡 Demand Soft           │ │
│  │  ↗ +2.1pts│  ↘ -3.2pts│ ↘ -8%   │                           │ │
│  └──────────┴──────────┴──────────┴───────────────────────────┘ │
│                                                                   │
│  Primary Drivers (Last 7 Days)                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ [!] Market Demand Contraction              Confidence: 95% │ │
│  │     Evidence: Organic CVR -11%, Ad CVR -9%, CPC stable     │ │
│  │     Impact: -12% total revenue                             │ │
│  │     → Recommendation: Contract spend 15%, hold exact match │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ [⚠] Organic Rank Decay — 3 ASINs              Medium       │ │
│  │     Top ASIN: B0DSFZK5W7 (-22% sessions, BSR +5.7k)       │ │
│  │     Impact: -180 AED/day revenue                           │ │
│  │     → Recommendation: Launch defense campaigns             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ [✓] Optimizations Performing Well          14 validated   │ │
│  │     Win rate: 86% (12/14 outperformed market)             │ │
│  │     Avg impact: +11pts ROAS vs baseline                    │ │
│  │     → Continue current strategies                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  [View All Signals →] [Review Validations →]                    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 4.2 Forward Signals Page

```
┌──────────────────────────────────────────────────────────────────┐
│  Diagnostics / Forward Signals                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Filters: [Severity: All ▼] [Type: All ▼] [Time: 7 days ▼]      │
│  Sort by: [Severity ▼]                                           │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 🔴 Market Demand Contraction       Confidence: 95%         │ │
│  │    Active for 5 days                                       │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ Evidence:                                                   │ │
│  │   • Organic CVR: -11% (3.2% → 2.8%)                        │ │
│  │   • Ad CVR: -9% (3.5% → 3.2%)                              │ │
│  │   • CPC: +1% (stable)                                      │ │
│  │   • Total Revenue: -12%                                    │ │
│  │                                                             │ │
│  │ Impact: -520 AED/day revenue                               │ │
│  │                                                             │ │
│  │ Diagnosis:                                                  │ │
│  │ Market-wide conversion decline affecting organic and paid  │ │
│  │ equally. Your optimization actions are NOT the cause.      │ │
│  │                                                             │ │
│  │ Recommended Actions:                                        │ │
│  │  1. Contract discovery spend 15-20% to preserve TACOS      │ │
│  │  2. Maintain exact match harvested campaigns (defensive)   │ │
│  │  3. Monitor for 7 days before further reductions           │ │
│  │                                                             │ │
│  │ [View Trend Chart] [Dismiss] [Mark as Reviewed]           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 🟡 Organic Rank Decay — ASIN B0DSFZK5W7  Confidence: 88%  │ │
│  │    Active for 3 days                                       │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ Evidence:                                                   │ │
│  │   • Sessions: -22% (85 → 66/day)                           │ │
│  │   • BSR: 12,450 → 18,200 (worse by 5,750)                 │ │
│  │   • Buy Box: 95% (stable — not pricing)                   │ │
│  │   • Organic CVR: Stable at 9.8%                            │ │
│  │                                                             │ │
│  │ ... [collapsed for space] ...                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 4.3 Optimization Validation Page

```
┌──────────────────────────────────────────────────────────────────┐
│  Diagnostics / Optimization Validation                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┬──────────┬──────────┬────────────────────────────┐ │
│  │Last 30 Days│Win Rate│Avg Impact│Top Performer               │ │
│  │42 actions│  81%   │  +9.2pts │ Harvest: +22pts avg        │ │
│  │          │(34/42) │          │                            │ │
│  └──────────┴──────────┴──────────┴────────────────────────────┘ │
│                                                                   │
│  Action Type Breakdown                                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Action Type      Total  Wins  Neutral  Loss  Win Rate %   │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ Harvest Created    8      7      1       0      88%       │ │
│  │ Bid Decrease      14     12      1       1      86%       │ │
│  │ Negative Added    12     10      2       0      83%       │ │
│  │ Bid Increase       5      3      1       1      60%       │ │
│  │ Budget Cut         3      2      0       1      67%       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Recent Validations                                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Feb 15 • Bid Decrease -30% • Brand Defense Exact           │ │
│  │ Target: protein powder [exact]                             │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ Treated:  ROAS 1.8 → 2.4 (+33%)                            │ │
│  │ Account:  ROAS -8% (market declined)                       │ │
│  │ Impact:   +41pts (Massively outperformed)                  │ │
│  │ Status:   ✅ OUTPERFORMED                                   │ │
│  │                                                             │ │
│  │ [View Details] [View Campaign →]                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Feb 12 • Harvest Created • Harvest-Whey-Exact              │ │
│  │ Targeting: 8 exact match keywords from broad campaigns     │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ Treated:  New campaign ROAS 3.2 (7-day avg)                │ │
│  │ Account:  ROAS -5% (slight market decline)                 │ │
│  │ Impact:   +28pts (Strong performer)                        │ │
│  │ Status:   ✅ OUTPERFORMED                                   │ │
│  │                                                             │ │
│  │ [View Details] [View Campaign →]                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 4.4 Trends & Correlations Page

```
┌──────────────────────────────────────────────────────────────────┐
│  Diagnostics / Trends & Correlations                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Time Range: [Last 60 Days ▼]                                    │
│                                                                   │
│  Revenue Breakdown                                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  7k ┤                 [Stacked Area Chart]                 │ │
│  │     │     ╱╲          Organic Revenue (top area)           │ │
│  │  6k ┤    ╱  ╲    ╱╲   Ad Revenue (bottom area)             │ │
│  │     │   ╱    ╲  ╱  ╲                                        │ │
│  │  5k ┤  ╱      ╲╱    ╲   ╱╲                                 │ │
│  │     │ ╱              ╲ ╱  ╲                                │ │
│  │  4k ┤╱                ╲    ╲                               │ │
│  │     └─────────────────────────────────────────────────────│ │
│  │     Dec 1         Jan 1           Feb 1         Feb 17    │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  TACOS vs Organic Share                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  35%┤                [Dual Axis Line Chart]           70% │ │
│  │     │    ╱╲          TACOS (left axis)               ╱    │ │
│  │  30%┤   ╱  ╲    ╱╲   Organic % (right axis)         ╱ 65% │ │
│  │     │  ╱    ╲  ╱  ╲                                 ╱      │ │
│  │  25%┤ ╱      ╲╱    ╲  ╱╲                          ╱  60% │ │
│  │     │╱              ╲╱  ╲                        ╱       │ │
│  │  20%┤                    ╲                      ╱   55% │ │
│  │     └─────────────────────────────────────────────────────│ │
│  │     Dec 1         Jan 1           Feb 1         Feb 17    │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────┬─────────────────────────────┐ │
│  │ CVR Comparison              │ BSR Trend — Top 5 ASINs     │ │
│  │ [Line chart: Org vs Paid]   │ [Multi-line BSR chart]      │ │
│  └─────────────────────────────┴─────────────────────────────┘ │
│                                                                   │
│  Correlation Matrix                                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              TACOS  Org %  Ad CVR  Org CVR  BSR            │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ TACOS         1.00  -0.82   0.31  -0.15   0.42            │ │
│  │ Organic %    -0.82   1.00  -0.28   0.41  -0.67            │ │
│  │ Ad CVR        0.31  -0.28   1.00   0.89  -0.22            │ │
│  │ Organic CVR  -0.15   0.41   0.89   1.00  -0.51            │ │
│  │ Avg BSR       0.42  -0.67  -0.22  -0.51   1.00            │ │
│  │                                                             │ │
│  │ Strong correlations (|r| > 0.7):                           │ │
│  │   • TACOS ↔ Organic %: -0.82 (inverse — as expected)      │ │
│  │   • Ad CVR ↔ Org CVR: +0.89 (move together — demand)      │ │
│  │   • Organic % ↔ BSR: -0.67 (rank up = share up)           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Responsive Design

### 5.1 Breakpoints

```css
:root {
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --breakpoint-2xl: 1536px;
}

/* Mobile First Approach */

/* Tablet */
@media (min-width: 768px) {
  .grid-2 {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .grid-3 {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .grid-4 {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* Large Desktop */
@media (min-width: 1280px) {
  .container {
    max-width: 1400px;
  }
}
```

### 5.2 Mobile Optimizations

**Stack metric cards vertically:**
```css
@media (max-width: 767px) {
  .metric-grid {
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }
  
  .signal-card {
    padding: var(--space-4);
  }
  
  .signal-actions {
    flex-direction: column;
  }
  
  .btn {
    width: 100%;
    justify-content: center;
  }
}
```

---

## 6. Animation & Transitions

### 6.1 Standard Transitions

```css
:root {
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 300ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 500ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Hover transitions */
.interactive {
  transition: all var(--transition-base);
}

/* Page transitions */
.fade-in {
  animation: fadeIn var(--transition-base) ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### 6.2 Loading States

```css
.skeleton {
  background: linear-gradient(90deg,
                rgba(255, 255, 255, 0.05) 25%,
                rgba(255, 255, 255, 0.1) 50%,
                rgba(255, 255, 255, 0.05) 75%);
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}
```

---

## 7. Streamlit Integration

### 7.1 Custom CSS Injection

```python
# pages/diagnostics.py
import streamlit as st

def inject_custom_css():
    """Load custom glassmorphic styles."""
    css = """
    <style>
    /* Import design system */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Root variables */
    :root {
      --primary-500: #3b82f6;
      --accent-500: #8b5cf6;
      /* ... all other variables */
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom components */
    .metric-card { ... }
    .signal-card { ... }
    /* ... all component CSS */
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# Call at top of every diagnostic page
inject_custom_css()
```

### 7.2 Component Rendering

```python
def render_overview():
    """Render overview page with glassmorphic components."""
    st.title("Diagnostics")
    
    # Metric cards
    cols = st.columns(4)
    with cols[0]:
        st.markdown(
            metric_card(
                label="TACOS",
                value="28.2%",
                delta="+2.1pts vs 7d avg",
                delta_type="negative",
                icon="percent"
            ),
            unsafe_allow_html=True
        )
    
    # Signal cards
    st.markdown("### Primary Drivers")
    signals = get_active_signals(limit=3)
    for signal in signals:
        st.markdown(
            render_signal_card(signal),
            unsafe_allow_html=True
        )
```

---

*Frontend architecture v1.0 — production-ready glassmorphic design system.*
