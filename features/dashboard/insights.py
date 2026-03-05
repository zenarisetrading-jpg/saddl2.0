"""
Homepage Intelligence Briefing
================================
Deterministic prose generator, LLM context formatter, and LLM caller.
Used by ui/layout.py → render_home() (Phase 3 homepage redesign).

Public surface:
    score_to_label(score)               → "Excellent" / "Good" / "Stable" / "At Risk" / "Critical"
    score_to_color(score)               → hex colour string
    generate_deterministic_briefing(m)  → 2-3 sentence template-driven prose, no LLM
    format_llm_context(m)               → structured plain-text block for LLM prompt
    call_homepage_llm(context, name)    → Claude / OpenAI response string
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ── Score bands: (min-threshold, label, hex-color) ───────────────────────────
_SCORE_BANDS = [
    (85, "Excellent", "#10B981"),
    (70, "Good",      "#34D399"),
    (50, "Stable",    "#F59E0B"),
    (35, "At Risk",   "#F97316"),
    (0,  "Critical",  "#EF4444"),
]


def score_to_label(score: float) -> str:
    """Return a human-readable status label for a 0-100 health score."""
    for threshold, label, _ in _SCORE_BANDS:
        if score >= threshold:
            return label
    return "Critical"


def score_to_color(score: float) -> str:
    """Return the hex colour matching a health score band."""
    for threshold, _, color in _SCORE_BANDS:
        if score >= threshold:
            return color
    return "#EF4444"


# ── Deterministic briefing ────────────────────────────────────────────────────

def generate_deterministic_briefing(metrics: Dict[str, Any]) -> str:
    """
    Build a 2-3 sentence intelligence briefing from template logic only.
    No LLM call — always fast and deterministic.

    Expected keys in *metrics*:
        health_score            float  0-100
        tacos_current           float | None   e.g. 0.082
        target_tacos            float          e.g. 0.10
        revenue_30d             float
        organic_share_pct       float | None   e.g. 42.0  (percentage, not ratio)
        attributed_impact       float          attributed AED from optimizer actions
        optimizer_total_actions int
        currency                str            e.g. "AED"
    """
    score         = float(metrics.get("health_score") or 0)
    tacos         = metrics.get("tacos_current")
    target_tacos  = float(metrics.get("target_tacos") or 0.10)
    revenue_30d   = float(metrics.get("revenue_30d") or 0)
    organic_pct   = metrics.get("organic_share_pct")
    attributed    = float(metrics.get("attributed_impact") or 0)
    total_actions = int(metrics.get("optimizer_total_actions") or 0)
    currency      = str(metrics.get("currency") or "AED")
    label         = score_to_label(score)

    parts: list[str] = []

    # Sentence 1 — overall health + revenue
    if revenue_30d > 0:
        parts.append(
            f"Account health is **{label.lower()}** at {score:.0f}/100, "
            f"with {currency} {revenue_30d:,.0f} in total sales over the past 30 days."
        )
    else:
        parts.append(f"Account health is **{label.lower()}** at {score:.0f}/100.")

    # Sentence 2 — biggest metric driver (TACOS-first, then organic share)
    if tacos is not None and target_tacos:
        diff_pct = (tacos - target_tacos) / target_tacos * 100
        if diff_pct > 10:
            parts.append(
                f"TACOS is running at {tacos * 100:.1f}% against a {target_tacos * 100:.1f}% target — "
                f"reducing ad spend as a share of revenue is the primary opportunity."
            )
        elif diff_pct < -10:
            parts.append(
                f"TACOS is healthy at {tacos * 100:.1f}% vs {target_tacos * 100:.1f}% target — "
                f"efficiency headroom may support more aggressive growth investment."
            )
        elif organic_pct is not None:
            direction = "strong brand pull" if organic_pct >= 40 else "room to grow organic share"
            parts.append(
                f"Organic revenue represents {organic_pct:.0f}% of total sales, "
                f"reflecting {direction}."
            )
    elif organic_pct is not None:
        direction = "strong brand pull" if organic_pct >= 40 else "room to grow organic share"
        parts.append(
            f"Organic revenue represents {organic_pct:.0f}% of total sales, "
            f"reflecting {direction}."
        )

    # Sentence 3 — optimizer / impact signal
    if attributed > 0 and total_actions > 0:
        act_word = "optimization" if total_actions == 1 else "optimizations"
        parts.append(
            f"The Optimizer has logged {total_actions:,} {act_word} "
            f"with {currency} {attributed:,.0f} in attributed impact."
        )
    elif total_actions > 0:
        act_word = "optimization" if total_actions == 1 else "optimizations"
        parts.append(
            f"The Optimizer has logged {total_actions:,} {act_word} — "
            f"impact windows are still maturing."
        )

    return "  \n".join(parts) if parts else (
        "Awaiting sufficient data to generate an account briefing."
    )


# ── LLM context formatter ─────────────────────────────────────────────────────

def format_llm_context(metrics: Dict[str, Any]) -> str:
    """
    Format a metrics dict into a structured plain-text block for an LLM prompt.
    """
    score         = float(metrics.get("health_score") or 0)
    label         = score_to_label(score)
    tacos         = metrics.get("tacos_current")
    target_tacos  = float(metrics.get("target_tacos") or 0.10)
    revenue_30d   = float(metrics.get("revenue_30d") or 0)
    revenue_prev  = float(metrics.get("revenue_prev_30d") or 0)
    organic_pct   = metrics.get("organic_share_pct")
    avg_cover     = metrics.get("avg_days_cover")
    attributed    = float(metrics.get("attributed_impact") or 0)
    total_actions = int(metrics.get("optimizer_total_actions") or 0)
    win_rate      = float(metrics.get("win_rate") or 0)
    currency      = str(metrics.get("currency") or "AED")
    account_name  = str(metrics.get("account_name") or "this account")
    last_refresh  = str(metrics.get("last_refresh_date") or "unknown")

    lines = [
        f"ACCOUNT: {account_name}",
        f"LAST DATA DATE: {last_refresh}",
        f"HEALTH SCORE: {score:.0f}/100 ({label})",
        f"REVENUE (30D): {currency} {revenue_30d:,.0f}",
    ]

    if revenue_prev > 0:
        delta_pct = (revenue_30d - revenue_prev) / revenue_prev * 100
        lines.append(f"REVENUE PREV 30D: {currency} {revenue_prev:,.0f} ({delta_pct:+.1f}%)")

    if tacos is not None:
        lines.append(f"TACOS: {tacos * 100:.2f}%  (target: {target_tacos * 100:.1f}%)")

    if organic_pct is not None:
        lines.append(f"ORGANIC REVENUE SHARE: {organic_pct:.1f}%")

    if avg_cover is not None:
        lines.append(f"FBA DAYS OF COVER: {avg_cover:.1f} days")

    lines.append(f"OPTIMIZER ACTIONS (TOTAL): {total_actions:,}")

    if attributed > 0:
        lines.append(f"ATTRIBUTED IMPACT (14D): {currency} {attributed:,.0f}")

    if win_rate > 0:
        lines.append(f"WIN RATE: {win_rate:.0f}%")

    return "\n".join(lines)


# ── LLM caller ────────────────────────────────────────────────────────────────

def call_homepage_llm(context_text: str, account_name: str = "this account") -> str:
    """
    Call Claude (preferred) or OpenAI for a structured strategic analysis.

    Returns a JSON string with three keys:
        key_achievements  — list of 3 specific positive findings
        areas_to_monitor  — list of 2-3 risks / concerns
        recommended_actions — list of 3 concrete, prioritised actions

    On failure returns a plain-text error string (callers must check for '{').

    API keys are sourced from st.secrets (cloud) or environment variables (local):
        CLAUDE_API_KEY   — Anthropic Claude (preferred)
        OPENAI_API_KEY   — OpenAI GPT-4o  (fallback)
    """
    import os
    import requests  # type: ignore
    import streamlit as st

    _SYSTEM = (
        "You are a senior Amazon PPC strategist analysing a Seller Central account. "
        "Based on the live performance metrics provided, return ONLY valid JSON — "
        "no markdown fences, no explanatory text outside the JSON — with this exact structure:\n"
        "{\n"
        '  "key_achievements": ["<1-2 sentence finding with numbers>", "<finding>", "<finding>"],\n'
        '  "areas_to_monitor": ["<1-2 sentence risk/concern with numbers>", "<risk>"],\n'
        '  "recommended_actions": ["<specific actionable step with numbers>", "<action>", "<action>"]\n'
        "}\n"
        "Rules:\n"
        "- Every item must reference at least one specific metric or number from the data.\n"
        "- key_achievements: 3 items — what is genuinely working.\n"
        "- areas_to_monitor: 2-3 items — risks, gaps, or anomalies that need attention.\n"
        "- recommended_actions: 3 items — prioritised, concrete next steps the team should take.\n"
        "- Do NOT use bullet characters inside the strings. Use plain prose sentences.\n"
        "- Return ONLY the JSON object, nothing else."
    )

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Account: {account_name}\n\n"
                f"Live metrics:\n{context_text}\n\n"
                "Return the JSON analysis now."
            ),
        },
    ]

    # ── Try Claude ────────────────────────────────────────────────────────────
    claude_key: Optional[str] = None
    try:
        claude_key = st.secrets.get("CLAUDE_API_KEY")
    except Exception:
        pass
    if not claude_key:
        claude_key = os.environ.get("CLAUDE_API_KEY")

    if claude_key:
        try:
            claude_msgs = [m for m in messages if m["role"] != "system"]
            system_msg  = next(
                (m["content"] for m in messages if m["role"] == "system"), None
            )
            payload: Dict[str, Any] = {
                "model":       "claude-3-5-sonnet-20241022",
                "max_tokens":  900,
                "temperature": 0.3,
                "messages":    claude_msgs,
            }
            if system_msg:
                payload["system"] = system_msg
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":          claude_key,
                    "anthropic-version":  "2023-06-01",
                    "Content-Type":       "application/json",
                },
                json=payload,
                timeout=45,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except Exception:
            pass  # fall through to OpenAI

    # ── Fall back to OpenAI ───────────────────────────────────────────────────
    openai_key: Optional[str] = None
    try:
        openai_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not openai_key:
        openai_key = os.environ.get("OPENAI_API_KEY")

    if openai_key:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":            "gpt-4o",
                    "messages":         messages,
                    "temperature":      0.3,
                    "max_tokens":       900,
                    "response_format":  {"type": "json_object"},
                },
                timeout=45,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"⚠️ AI analysis failed: {exc}"

    return (
        "⚠️ No AI API key configured. "
        "Add CLAUDE_API_KEY or OPENAI_API_KEY to .streamlit/secrets.toml."
    )


def parse_analysis_sections(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse the JSON returned by call_homepage_llm into a dict.
    Returns None if the text is not valid JSON (e.g. an error string).
    """
    import json, re

    if not text or not text.strip().startswith("{"):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from within backtick fences
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None
