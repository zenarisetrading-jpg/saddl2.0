# SADDL — Phase 4 Pass 1 & 2 Pre-Deprecation Audit
Date: 2026-02-25
Scope: Diagnostics tab campaign/ad-group intelligence — what exists, what is reusable for Phase 4 Pass 1 (Campaign Layer) and Pass 2 (Ad Group Layer)
Audited files: `utils/diagnostics.py`, `features/diagnostics/control_center.py`, `features/optimizer_shared/intelligence.py`

Legend:
- `(A)` = reuse directly in Pass 1 / Pass 2 — copy/import as-is
- `(B)` = extend for Pass 1 / Pass 2 — right shape, wrong thresholds or missing output fields
- `(C)` = not relevant — no overlap with Pass 1/2 requirements

---

## Question 1 — Does Diagnostics identify underperforming campaigns by ROAS or efficiency threshold?

**Yes.** One function exists.

### Finding 1.1 — `identify_brutal_underperformers` — **(B) Extend for Pass 1**

**File:** `utils/diagnostics.py:1398–1451`
**Called by:** `generate_multi_dimensional_actions()` at line 1490, result placed in `actions["campaign_optimizations"]`
**Rendered in UI:** Campaign action cards inside Diagnostics Control Center

**Exact function signature:**
```python
def identify_brutal_underperformers(
    days: int = 30, limit: int = 10, client_id: str = CLIENT_ID
) -> List[Dict[str, Any]]:
```

**SQL query (exact):**
```sql
WITH campaign_performance AS (
  SELECT
    campaign_name,
    SUM(spend) AS total_spend,
    SUM(sales) AS total_sales,
    SUM(sales) / NULLIF(SUM(spend), 0) AS roas
  FROM public.raw_search_term_data
  WHERE report_date BETWEEN '{start_date}' AND '{anchor_date}'
    AND client_id = '{client_id}'
  GROUP BY campaign_name
  HAVING SUM(spend) > 100
)
SELECT
  campaign_name,
  total_spend,
  total_sales,
  roas,
  CASE
    WHEN roas < 2.5 THEN total_spend - (total_sales / 2.5)
    ELSE 0
  END AS estimated_waste,
  CASE
    WHEN roas < 1.0 AND total_sales < 500 THEN 'CUT'
    WHEN roas < 1.5 AND total_sales > 2000 THEN 'REVIEW'
    WHEN roas < 1.5 THEN 'CUT'
    WHEN roas < 2.0 THEN 'REVIEW'
    ELSE 'HEALTHY'
  END AS severity
FROM campaign_performance
WHERE (roas < 1.5 AND total_sales < 2000) OR roas < 1.0
ORDER BY total_spend DESC
LIMIT 10
```

**Output shape (returned list of dicts):**
```python
{
    "campaign": str,       # campaign_name
    "spend": float,        # total_spend in window
    "sales": float,        # total_sales in window
    "roas": float,         # computed ROAS
    "waste": float,        # estimated_waste at 2.5x target
    "severity": str,       # 'CUT' | 'REVIEW' | 'HEALTHY'
}
```

**What it does right for Pass 1:**
- Queries `raw_search_term_data` at campaign level — same source Pass 1 needs
- Computes ROAS per campaign — correct metric
- Has a severity label ('CUT' ≈ pause candidate; 'REVIEW' ≈ flag for bid-down) — maps to Pass 1's two tiers
- Has `estimated_waste` — closest existing proxy to "estimated weekly spend recovery"
- Is already parameterized on `client_id` and `days` — compatible with Pass 1's window logic

**Gaps that require extension for Pass 1:**
1. **Hardcoded ROAS threshold (1.5x)** — Pass 1 PRD requires `0.5 × target_roas` for pause; `0.5x–target_roas` for flag-and-bid-down. `target_roas` is per-client and must be passed in.
2. **Minimum spend threshold is AED 100 (total in window)** — Pass 1 PRD requires AED 500. Change `HAVING SUM(spend) > 100` to `HAVING SUM(spend) > 500`.
3. **No "pause recommendation" object** — returns a flat dict without a structured `recommendation_type: pause | flag` field. Pass 1 brief needs `pause_recommendation: bool` and `estimated_weekly_recovery: float`.
4. **`estimated_waste` is calculated against a hardcoded 2.5x ROAS target**, not against actual `target_roas`. Needs to be computed as `total_spend - (total_sales / target_roas)`.
5. **No annualized / weekly spend recovery** — currently returns window-total waste. Pass 1 needs weekly figure for the brief: `waste / days * 7`.
6. **ROAS scale candidate identification missing** — Pass 1 also wants campaigns with `ROAS > 1.5 × target_roas` flagged as scale candidates. Not in current function.
7. **Output not passed to optimizer or actions_log** — currently rendered as Diagnostics UI cards only. Pass 1 needs this data to flow into the pre-run brief and actions_log.

---

### Finding 1.2 — `generate_recommendations()` Rule 5 — **(C) Not relevant**

**File:** `utils/diagnostics.py:648–655`

```python
if health.get('tacos_change', 0) > 5 and health.get('sales_change_pct', 0) < 2:
    recommendations.append({
        'priority': 'IMMEDIATE',
        'action': 'Audit and pause bottom 20% of spend by ROAS',
        'reason': 'TACOS rising without revenue growth = waste',
    })
```

Generic account-level advice. No campaign list, no specific ROAS computation, no spend figures. Not reusable for Pass 1's per-campaign recommendation objects.

---

### Finding 1.3 — `generate_multi_dimensional_actions()` budget pacing — **(C) Not relevant**

**File:** `utils/diagnostics.py:1502–1510`

```python
if float(health.get("tacos_change", 0) or 0) > 3:
    actions["budget_pacing"] = [
        {"text": "Apply stricter daily caps on auto campaigns", ...},
        {"text": "Prioritize dayparts with higher CVR", ...},
    ]
```

Generic auto-campaign guidance. No campaign-level data. Not reusable for Pass 1.

---

## Question 2 — Does Diagnostics identify ad groups with zero conversion or below-average CVR?

**No.** There is no ad group level analysis anywhere in the Diagnostics system.

### Finding 2.1 — No ad group queries in `utils/diagnostics.py` — **(C) Build Pass 2 from scratch**

Every query in `utils/diagnostics.py` that touches `raw_search_term_data` groups only at `campaign_name` level. No query groups by `(campaign_name, ad_group_name)`.

Specifically confirmed absent:
- No `GROUP BY campaign_name, ad_group_name` in any diagnostics query
- No `SUM(orders) = 0` or CVR vs. account-average threshold at ad group level
- No ad group zero-conversion detection

**The underlying data exists.** `raw_search_term_data` contains `campaign_name`, `ad_group_name`, `orders`, `clicks`, `spend`, `sales`. Pass 2 queries can be built directly from this table.

---

### Finding 2.2 — `build_commerce_lookup` in optimizer intelligence — **(C) Not relevant for Pass 2**

**File:** `features/optimizer_shared/intelligence.py:71–100`

This function groups by `(campaign_name, ad_group_name)` and builds a lookup for INVENTORY_RISK / HALO_ACTIVE / CANNIBALIZE_RISK flags at ad group level. However:
- It operates on `commerce_metrics` dataframe (SP-API commerce data), not `raw_search_term_data`
- It measures organic CVR vs. paid CVR for halo/cannibalize detection
- It does NOT measure ad group PPC efficiency (ROAS, CVR vs account average, zero conversions)

Not reusable for Pass 2 but confirms the `(campaign_name, ad_group_name)` key pattern works in this codebase.

---

## Question 3 — Does Diagnostics produce campaign-level pause or budget recommendations?

**Partially.** There are diagnostic labels ('CUT'/'REVIEW') that conceptually mean "pause"/"review", but no structured pause recommendations and no data flow to the optimizer.

### Finding 3.1 — `generate_multi_dimensional_actions()` → `actions["campaign_optimizations"]` — **(B) Extend**

**File:** `utils/diagnostics.py:1490`

```python
actions["campaign_optimizations"] = identify_brutal_underperformers(
    days=days, client_id=client_id
)
```

The 'CUT' campaigns from `identify_brutal_underperformers` are surfaced in the Diagnostics UI as action cards (rendered by `components/diagnostic_cards.py:render_actions()`). The 'CUT'/'REVIEW' labels map semantically to Pass 1's pause / flag-for-bid-down tiers.

**Gap:** These are UI-only recommendations. There is no:
- Structured `pass_level: 'campaign'` field for actions_log
- Data flow from Diagnostics recommendations → Optimizer pre-run brief
- Campaign-level entries written to `actions_log`

---

## Summary Reuse Matrix

| Component | File | Lines | Pass 1 / Pass 2 | Rating |
|---|---|---|---|---|
| `identify_brutal_underperformers()` SQL | `utils/diagnostics.py` | 1398–1451 | Pass 1 — campaign ROAS identification | **(B) Extend** |
| Campaign dict output shape | `utils/diagnostics.py` | 1439–1451 | Pass 1 — pause recommendation objects | **(B) Extend** |
| `generate_multi_dimensional_actions()` campaign section | `utils/diagnostics.py` | 1488–1490 | Pass 1 — orchestration hook | **(B) Extend** |
| `generate_recommendations()` Rule 5 | `utils/diagnostics.py` | 648–655 | Pass 1 | **(C)** |
| Budget pacing actions | `utils/diagnostics.py` | 1502–1510 | Pass 1 | **(C)** |
| Ad group CVR / zero-conversion detection | `utils/diagnostics.py` | (absent) | Pass 2 | **(C) Build fresh** |
| `build_commerce_lookup()` ad group key pattern | `features/optimizer_shared/intelligence.py` | 71–100 | Pass 2 — key structure reference only | **(C)** |

---

## Phase 4 Build Instructions (from this audit)

### Pass 1 — Campaign Layer

**Extend `identify_brutal_underperformers()` or create `get_campaign_pass1_recommendations()`:**

Changes required:
1. Accept `target_roas: float` parameter (read from client settings)
2. Change `HAVING SUM(spend) > 100` → `HAVING SUM(spend) > 500`
3. Replace hardcoded 1.5x/1.0x thresholds with `0.5 * target_roas` (pause) and `target_roas` (flag)
4. Add `roas > 1.5 * target_roas` → scale candidate tier
5. Compute `estimated_weekly_recovery = GREATEST(total_spend - (total_sales / target_roas), 0) / days * 7`
6. Return structured objects with `recommendation_type: 'pause' | 'flag' | 'scale'` field
7. Add `pass_level = 'campaign'` field for actions_log insertion

**Source table:** `public.raw_search_term_data` (already used, no new dependencies)

### Pass 2 — Ad Group Layer

**Build `get_adgroup_pass2_recommendations()` from scratch:**

Suggested SQL structure:
```sql
WITH adgroup_performance AS (
  SELECT
    campaign_name,
    ad_group_name,
    SUM(spend) AS total_spend,
    SUM(sales) AS total_sales,
    SUM(orders) AS total_orders,
    SUM(clicks) AS total_clicks,
    SUM(orders)::FLOAT / NULLIF(SUM(clicks), 0) AS cvr
  FROM public.raw_search_term_data
  WHERE report_date BETWEEN '{start_date}' AND '{anchor_date}'
    AND client_id = '{client_id}'
  GROUP BY campaign_name, ad_group_name
),
account_avg_cvr AS (
  SELECT AVG(orders::FLOAT / NULLIF(clicks, 0)) AS avg_cvr
  FROM public.raw_search_term_data
  WHERE report_date BETWEEN '{start_date}' AND '{anchor_date}'
    AND client_id = '{client_id}'
    AND clicks > 0
)
SELECT
  a.campaign_name,
  a.ad_group_name,
  a.total_spend,
  a.total_orders,
  a.cvr,
  c.avg_cvr,
  a.cvr / NULLIF(c.avg_cvr, 0) AS cvr_ratio,
  CASE
    WHEN a.total_orders = 0 AND a.total_spend > 200 THEN 'ZERO_CONV'
    WHEN a.cvr < (c.avg_cvr * 0.20) AND a.total_spend > 300 THEN 'LOW_CVR'
    ELSE 'OK'
  END AS flag_type
FROM adgroup_performance a, account_avg_cvr c
WHERE
  (a.total_orders = 0 AND a.total_spend > 200)
  OR (a.cvr < (c.avg_cvr * 0.20) AND a.total_spend > 300)
ORDER BY a.total_spend DESC
```

Thresholds (from PRD):
- Zero conversions AND spend > AED 200 → `ZERO_CONV` flag
- CVR < 20% of account average AND spend > AED 300 → `LOW_CVR` flag
- Apply only within campaigns NOT flagged for pause in Pass 1

---

## Critical Pre-Build Note

The `identify_brutal_underperformers()` function is currently called inside `generate_multi_dimensional_actions()` which fires on every Diagnostics page load with no `@st.cache_data` decorator. When extracted for Pass 1, ensure the Pass 1 data fetch is:
- Called once during optimizer pre-run brief construction
- Not called on every Streamlit re-render
- Results stored in `st.session_state` for the duration of the optimizer session

---

## Audit Confirmation

This document was created prior to Phase 0 deprecation of the Diagnostics tab.
The `features/diagnostics/control_center.py` and `utils/diagnostics.py` files must not be deleted until this document is committed and the Phase 4 Pass 1 implementation has been verified against Finding 1.1.
