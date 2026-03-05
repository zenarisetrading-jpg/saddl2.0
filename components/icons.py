"""SVG icon helpers for diagnostics UI (draft only)."""

from __future__ import annotations


ICONS = {
    "trend_up": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 16L10 10L14 14L20 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 8H20V12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "trend_down": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 8L10 14L14 10L20 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 16H20V12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "neutral": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 12H20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "warning": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3L22 20H2L12 3Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 9V13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="17" r="1" fill="currentColor"/></svg>',
    "alert": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 8V12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="16" r="1" fill="currentColor"/></svg>',
    "spark": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    "money": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 6H20V18H4V6Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/></svg>',
    "layers": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3L3 8L12 13L21 8L12 3Z" stroke="currentColor" stroke-width="2"/><path d="M3 12L12 17L21 12" stroke="currentColor" stroke-width="2"/><path d="M3 16L12 21L21 16" stroke="currentColor" stroke-width="2"/></svg>',
    "eye": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/></svg>',
    "lightbulb": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 18h6m-5 3h4m4-11a6 6 0 1 0-12 0c0 2.2 1 3.3 2 4.5.8 1 1 1.5 1 2.5h6c0-1 .2-1.5 1-2.5 1-1.2 2-2.3 2-4.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "alert-circle": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 8v4m0 4h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "target": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>',
    "wallet": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="6" width="18" height="12" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 12h3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "box": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="m3 7 9-4 9 4-9 4-9-4Z" stroke="currentColor" stroke-width="2"/><path d="m3 7 9 4v10l-9-4V7Zm18 0-9 4" stroke="currentColor" stroke-width="2"/></svg>',
}


def render_icon(name: str, color: str = "currentColor", size: int = 18) -> str:
    """Return inline SVG wrapped for use in markdown HTML."""
    svg = ICONS.get(name, ICONS["neutral"])
    return (
        f'<span style="display:inline-flex;width:{size}px;height:{size}px;color:{color};'
        f'line-height:1;vertical-align:middle">{svg}</span>'
    )
