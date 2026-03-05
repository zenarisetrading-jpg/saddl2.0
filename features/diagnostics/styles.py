"""Glassmorphic design system for diagnostics pages."""

from __future__ import annotations

import streamlit as st


def inject_diagnostics_css() -> None:
    """Inject diagnostics-specific CSS variables and component classes."""
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

:root {
  --diag-bg-1: #071027;
  --diag-bg-2: #031a16;
  --diag-bg-3: #1f1026;
  --diag-glass: rgba(255, 255, 255, 0.06);
  --diag-glass-strong: rgba(255, 255, 255, 0.1);
  --diag-border: rgba(255, 255, 255, 0.18);
  --diag-text: #eaf0ff;
  --diag-muted: #a7b4d6;
  --diag-blue: #5ea7ff;
  --diag-cyan: #4ad7d1;
  --diag-amber: #f6b23f;
  --diag-red: #f26464;
  --diag-green: #38d39f;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(900px 450px at 10% 0%, rgba(94, 167, 255, 0.18) 0%, transparent 70%),
    radial-gradient(900px 500px at 95% -10%, rgba(56, 211, 159, 0.14) 0%, transparent 72%),
    linear-gradient(125deg, var(--diag-bg-1) 0%, var(--diag-bg-2) 45%, var(--diag-bg-3) 100%);
}

[data-testid="stAppViewContainer"] * {
  font-family: "Plus Jakarta Sans", sans-serif;
}

.diag-shell {
  position: relative;
  z-index: 2;
}

.diag-title-lg {
  font-family: "Space Grotesk", sans-serif;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--diag-text);
}

.diag-title-md {
  font-family: "Space Grotesk", sans-serif;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--diag-text);
}

.diag-text-sm {
  color: var(--diag-muted);
  font-size: 0.88rem;
  line-height: 1.45;
}

.diag-panel {
  background: linear-gradient(145deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03));
  backdrop-filter: blur(20px) saturate(165%);
  -webkit-backdrop-filter: blur(20px) saturate(165%);
  border: 1px solid var(--diag-border);
  border-radius: 20px;
  padding: 22px;
  box-shadow: 0 18px 50px rgba(3, 10, 28, 0.45), inset 0 1px 0 rgba(255,255,255,0.12);
}

.health-card {
  background: linear-gradient(145deg, rgba(86, 126, 255, 0.16) 0%, rgba(73, 226, 207, 0.07) 52%, rgba(255, 199, 90, 0.06) 100%);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 24px;
  padding: 28px;
  box-shadow: 0 24px 70px rgba(2, 8, 26, 0.55), inset 0 1px 0 rgba(255,255,255,0.16);
}

.diag-score {
  font-family: "Space Grotesk", sans-serif;
  font-size: 2.5rem;
  font-weight: 700;
  color: #f7fbff;
}

.diag-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  border: 1px solid rgba(255,255,255,0.18);
}

.diag-pill.healthy { color: #95f3cf; background: rgba(56, 211, 159, 0.16); }
.diag-pill.caution { color: #fbd484; background: rgba(246, 178, 63, 0.2); }
.diag-pill.declining,
.diag-pill.critical { color: #ffb0b0; background: rgba(242, 100, 100, 0.2); }

.health-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.12);
  overflow: hidden;
}

.health-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--diag-cyan), var(--diag-blue));
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.metric-card {
  padding: 14px;
  border-radius: 14px;
  background: rgba(5, 13, 33, 0.38);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.metric-label {
  color: var(--diag-muted);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.metric-value {
  margin-top: 4px;
  font-size: 1.12rem;
  font-weight: 700;
  color: var(--diag-text);
}

.metric-delta {
  margin-top: 3px;
  font-size: 0.78rem;
  font-weight: 600;
}

.metric-delta.pos { color: var(--diag-green); }
.metric-delta.neg { color: var(--diag-red); }
.metric-delta.neu { color: var(--diag-muted); }

.mini-health {
  margin-top: 7px;
  font-size: 0.72rem;
  color: var(--diag-muted);
}

.primary-box {
  margin-top: 18px;
  padding: 16px;
  border-radius: 14px;
  background: rgba(4, 12, 31, 0.44);
  border: 1px solid rgba(255,255,255,0.11);
}

.chart-card {
  background: rgba(7, 16, 38, 0.5);
  border: 1px solid rgba(255,255,255,0.11);
  border-radius: 18px;
  padding: 16px;
}

.chart-note {
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.24);
  border: 1px solid rgba(255,255,255,0.09);
}

.action-card {
  border-radius: 16px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(7, 16, 38, 0.45);
  backdrop-filter: blur(12px);
}

.action-card h4 {
  margin: 0 0 10px 0;
  color: var(--diag-text);
  font-size: 0.95rem;
}

.action-card ul {
  margin: 0;
  padding-left: 16px;
}

.action-card li {
  color: var(--diag-muted);
  margin-bottom: 6px;
  line-height: 1.4;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 22px 0 10px;
}

.section-kicker {
  color: var(--diag-muted);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.asin-table-wrap {
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px;
  overflow: hidden;
  background: rgba(5, 12, 30, 0.45);
}
.asin-toolbar {
  margin: 8px 0 10px;
  color: var(--diag-muted);
  font-size: 0.82rem;
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
        """,
        unsafe_allow_html=True,
    )
