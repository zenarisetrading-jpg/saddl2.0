# SADDL AdPulse — Diagnostic Intelligence Layer
## Product Requirements Document v2.0 (Revised)

**Status:** Ready for Build  
**Author:** SADDL Product  
**Date:** February 2026  
**Revision:** Removed validation/impact tracking (already exists), focused on organic+paid intelligence

---

## 1. Executive Summary

### 1.1 Problem Statement

SADDL's existing Impact Dashboard already validates whether optimizations worked by measuring before/after performance. However, it cannot answer two critical upstream questions:

**Question 1 — Root Cause:**  
When ROAS declines, is it:
- A PPC problem (bad bids, wrong targets, over-negation)?
- An organic problem (rank decay, listing suppression)?
- A market problem (demand contraction affecting all channels)?

**Question 2 — Opportunity Identification:**  
Where should you act next:
- Defend declining organic rank with ads?
- Scale high-performing organic ASINs into paid?
- Contract spend due to market decline?
- Expand discovery to offset harvest cannibalization?

### 1.2 Solution Overview

The Diagnostic Intelligence Layer adds a new lens on top of existing SADDL data:
- **Seller Central data** (total revenue, organic traffic, BSR) from SP-API
- **Ad Console data** (spend, attributed sales, performance) from existing tables
- **Impact Dashboard data** (optimization results) from existing pipeline

And produces:
- **Root Cause Diagnosis:** Separates PPC vs organic vs market issues
- **Forward Signals:** Opportunities ranked by impact and confidence
- **Trend Analysis:** Multi-metric correlation to surface patterns

### 1.3 Scope Boundaries

**IN SCOPE:**
- Signal detection (demand contraction, organic decay, opportunities)
- Root cause decomposition (DuPont ROAS analysis)
- Trend visualization combining organic + paid metrics
- Integration with existing Impact Dashboard for context

**OUT OF SCOPE (Already Exists):**
- Optimization action logging (Impact Dashboard handles this)
- Before/after validation (Impact Dashboard handles this)
- Win rate tracking (Impact Dashboard handles this)
- Optimization recommendation engine (Phase 2, separate build)

---

## 2. Data Sources

### 2.1 Existing Data (No Changes)

| Source | Schema.Table | Owner | Usage |
|---|---|---|---|
| Ad Console | public.raw_search_term_data | Existing | Daily spend/sales by search term |
| Ad Console | public.target_stats | Existing | Weekly performance by target |
| Impact Dashboard | [table_name_tbd] | Existing | Optimization results, win rates |

### 2.2 New Data Required

#### 2.2.1 Seller Central — Sales & Traffic

**Already implemented** via SP-API pipeline built today.

**Tables:**
- `sc_raw.sales_traffic` — ASIN-level daily data (✅ populated)
- `sc_analytics.account_daily` — Account-level rollup (✅ computed)

#### 2.2.2 Seller Central — BSR (Best Seller Rank)

**NEW — Requires implementation in Phase 1.**

**Endpoint:** `/catalog/2022-04-01/items/{asin}`  
**Fields:** `salesRankings` (category, rank)  
**Frequency:** Daily pull for all active ASINs

**Storage:**

```sql
CREATE TABLE sc_raw.bsr_history (
    id                  BIGSERIAL PRIMARY KEY,
    report_date         DATE NOT NULL,
    marketplace_id      VARCHAR(20) NOT NULL,
    asin                VARCHAR(20) NOT NULL,
    category_name       VARCHAR(200),
    category_id         VARCHAR(100),
    rank                INTEGER,
    pulled_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_date, marketplace_id, asin, category_id)
);

CREATE INDEX idx_bsr_date_asin ON sc_raw.bsr_history (report_date, asin);
```

**Computed View — BSR Trend:**

```sql
CREATE VIEW sc_analytics.bsr_trends AS
SELECT 
    b.asin,
    b.report_date,
    b.rank as current_rank,
    LAG(b.rank, 7) OVER w as rank_7d_ago,
    LAG(b.rank, 30) OVER w as rank_30d_ago,
    b.rank - LAG(b.rank, 7) OVER w as rank_change_7d,
    CASE 
        WHEN b.rank < LAG(b.rank, 7) OVER w THEN 'IMPROVING'
        WHEN b.rank > LAG(b.rank, 7) OVER w * 1.1 THEN 'DECLINING'
        ELSE 'STABLE'
    END as rank_status_7d
FROM sc_raw.bsr_history b
WHERE b.category_name IS NOT NULL
WINDOW w AS (PARTITION BY b.asin, b.category_id ORDER BY b.report_date);
```

**Pipeline:** `pipeline/bsr_pipeline.py`
- Runs daily after SC sales/traffic pipeline
- Pulls BSR for all ASINs with activity in last 7 days
- Rate limit: 5 req/sec (Catalog Items API)
- Estimated runtime: ~20 seconds for 100 ASINs

---

## 3. Signal Detection Patterns

### 3.1 Signal 1: Market Demand Contraction

**Purpose:** Detect when declining performance is a market problem, not a PPC problem.

**Detection Logic:**

```sql
CREATE VIEW sc_analytics.signal_demand_contraction AS
WITH recent AS (
    SELECT 
        report_date,
        total_ordered_revenue,
        organic_share_pct,
        tacos
    FROM sc_analytics.account_daily
    WHERE report_date >= CURRENT_DATE - 14
),
organic_cvr AS (
    SELECT 
        report_date,
        AVG(unit_session_percentage) as avg_organic_cvr
    FROM sc_raw.sales_traffic
    WHERE report_date >= CURRENT_DATE - 14
    GROUP BY report_date
),
ad_metrics AS (
    SELECT 
        report_date,
        AVG(spend / NULLIF(clicks, 0)) as avg_cpc,
        SUM(orders) / NULLIF(SUM(clicks), 0) * 100 as ad_cvr
    FROM public.raw_search_term_data
    WHERE report_date >= CURRENT_DATE - 14
      AND client_id = 's2c_uae_test'
    GROUP BY report_date
)
SELECT 
    r.report_date,
    r.total_ordered_revenue,
    o.avg_organic_cvr,
    a.ad_cvr,
    a.avg_cpc,
    -- Pattern: both CVRs declining + CPC stable = demand problem
    CASE 
        WHEN o.avg_organic_cvr < LAG(o.avg_organic_cvr, 7) OVER w * 0.9
         AND a.ad_cvr < LAG(a.ad_cvr, 7) OVER w * 0.9
         AND a.avg_cpc BETWEEN LAG(a.avg_cpc, 7) OVER w * 0.95 AND LAG(a.avg_cpc, 7) OVER w * 1.05
        THEN TRUE
        ELSE FALSE
    END as is_demand_contraction,
    -- Compute severity
    (o.avg_organic_cvr / NULLIF(LAG(o.avg_organic_cvr, 7) OVER w, 0) - 1) * 100 as organic_cvr_change_pct,
    (a.ad_cvr / NULLIF(LAG(a.ad_cvr, 7) OVER w, 0) - 1) * 100 as ad_cvr_change_pct
FROM recent r
JOIN organic_cvr o USING (report_date)
JOIN ad_metrics a USING (report_date)
WINDOW w AS (ORDER BY r.report_date)
ORDER BY r.report_date DESC;
```

**Alert Trigger:**  
`is_demand_contraction = TRUE` for 3+ consecutive days

**Severity Levels:**
- **Critical:** Both CVRs down >15%
- **High:** Both CVRs down 10-15%
- **Medium:** Both CVRs down 5-10%

**UI Output:**

```
⚠️ Market Demand Contraction Detected

Severity: High
Duration: 5 days
Confidence: 95%

Evidence:
• Organic CVR: -11% (3.2% → 2.8%)
• Ad CVR: -9% (3.5% → 3.2%)
• CPC: +1% (stable, no bid war)
• Total Revenue: -12%

Diagnosis:
Market-wide conversion decline affecting both organic and paid equally.
This is NOT a PPC problem — your optimizations are not the cause.

Recommended Actions:
1. Contract discovery spend 15-20% to preserve TACOS
2. Maintain exact match harvested campaigns (defensive)
3. Monitor for 7 days before further action
4. Do NOT attempt to optimize your way out — demand is external

Impact Dashboard Reference:
Recent optimizations show 86% win rate despite market decline,
confirming actions are effective within deteriorating conditions.
```

---

### 3.2 Signal 2: Organic Rank Decay

**Purpose:** Detect when ASINs are losing organic rank and need ad defense.

**Detection Logic:**

```sql
CREATE VIEW sc_analytics.signal_organic_decay AS
WITH asin_trends AS (
    SELECT 
        st.child_asin,
        st.report_date,
        st.sessions,
        st.buy_box_percentage,
        st.ordered_revenue,
        LAG(st.sessions, 7) OVER w as sessions_7d_ago,
        LAG(st.buy_box_percentage, 7) OVER w as bb_7d_ago,
        b.rank as current_bsr,
        b.rank_7d_ago,
        b.rank_status_7d
    FROM sc_raw.sales_traffic st
    LEFT JOIN sc_analytics.bsr_trends b 
        ON st.child_asin = b.asin 
        AND st.report_date = b.report_date
    WHERE st.report_date >= CURRENT_DATE - 14
    WINDOW w AS (PARTITION BY st.child_asin ORDER BY st.report_date)
)
SELECT 
    child_asin,
    report_date,
    sessions,
    sessions_7d_ago,
    (sessions - sessions_7d_ago) / NULLIF(sessions_7d_ago, 0) * 100 as session_change_pct,
    current_bsr,
    rank_7d_ago,
    rank_status_7d,
    ordered_revenue,
    buy_box_percentage,
    -- Detect: sessions down + BSR worsening + buybox stable
    CASE 
        WHEN sessions < sessions_7d_ago * 0.85  -- Sessions down 15%+
         AND rank_status_7d = 'DECLINING'
         AND buy_box_percentage > 90  -- Still winning buy box
         AND ordered_revenue > 100  -- Material revenue
        THEN TRUE
        ELSE FALSE
    END as is_rank_decay
FROM asin_trends
WHERE sessions_7d_ago IS NOT NULL
ORDER BY session_change_pct ASC;
```

**Alert Trigger:**  
ASINs with `is_rank_decay = TRUE` and revenue >500 AED/week

**Severity:**
- **High:** Revenue at risk >1000 AED/week, sessions down >20%
- **Medium:** Revenue 500-1000 AED/week, sessions down 15-20%
- **Low:** Revenue <500 AED/week, sessions down <15%

**UI Output:**

```
🔴 Organic Rank Decay — ASIN B0DSFZK5W7

Severity: High
Revenue at Risk: 1,200 AED/week
Confidence: 88%

Evidence:
• Sessions: -22% (85 → 66/day)
• BSR: 12,450 → 18,200 (worse by 5,750 positions)
• Buy Box: 95% (stable — not a pricing issue)
• Organic CVR: Stable at 9.8%

Diagnosis:
Product is losing organic rank despite winning buy box and maintaining
conversion rate. Likely causes: competitor launched similar product,
review velocity slowed, or Amazon algorithm shift.

Immediate Action:
→ Launch exact match defense campaign for this ASIN
→ Target: brand + product keywords, high bids
→ Goal: Hold position while investigating root cause

Root Cause Investigation:
→ Check recent review velocity (has it slowed?)
→ Scan for new competitors in category (launched last 30 days?)
→ Review content quality score in Seller Central
→ Check for suppression or listing issues

Impact Dashboard Reference:
Previous brand defense campaigns for this ASIN showed +28pts ROAS
vs market baseline, validating this approach.
```

---

### 3.3 Signal 3: Non-Advertised High Performers

**Purpose:** Identify high-performing organic ASINs that should be tested with ads.

**Detection Logic:**

```sql
CREATE VIEW sc_analytics.signal_non_advertised_winners AS
WITH sc_performance AS (
    SELECT 
        child_asin,
        SUM(ordered_revenue) as revenue_30d,
        SUM(units_ordered) as units_30d,
        AVG(unit_session_percentage) as avg_cvr,
        AVG(sessions) as avg_sessions_per_day
    FROM sc_raw.sales_traffic
    WHERE report_date >= CURRENT_DATE - 30
    GROUP BY child_asin
),
advertised_asins AS (
    -- ASINs with ad activity in last 30 days
    SELECT DISTINCT asin
    FROM public.advertised_product_ca...  -- Use actual table name
    WHERE report_date >= CURRENT_DATE - 30
)
SELECT 
    sp.child_asin,
    sp.revenue_30d,
    sp.units_30d,
    sp.avg_cvr,
    sp.avg_sessions_per_day,
    sp.revenue_30d / 30 as avg_daily_revenue,
    -- Scoring for prioritization
    CASE 
        WHEN sp.avg_cvr > 8 AND sp.revenue_30d > 2000 THEN 'HIGH'
        WHEN sp.avg_cvr > 5 AND sp.revenue_30d > 1000 THEN 'MEDIUM'
        ELSE 'LOW'
    END as priority
FROM sc_performance sp
LEFT JOIN advertised_asins aa ON sp.child_asin = aa.asin
WHERE aa.asin IS NULL  -- Not advertised
  AND sp.revenue_30d > 500
ORDER BY sp.revenue_30d DESC;
```

**Alert Trigger:**  
ASINs with priority IN ('HIGH', 'MEDIUM')

**UI Output:**

```
💡 High-Performing Organic ASIN — Test Advertising

ASIN: B0CN3GBVZ6
Priority: High
Current Status: Not advertised (100% organic)

30-Day Performance:
• Revenue: 3,200 AED (organic only)
• Units: 85
• Avg CVR: 11.2% (excellent)
• Sessions/day: 34

Opportunity:
This ASIN converts well organically. Advertising could scale volume
while maintaining efficiency.

Recommended Test:
→ Launch Auto campaign with conservative budget (50 AED/day)
→ Run for 14 days to measure incremental impact
→ Track: Does total ASIN revenue grow, or do ads cannibalize organic?

Expected Outcome:
If ad sales = +40 AED/day and organic holds steady,
total ASIN revenue = +1,200 AED/month with minimal TACOS impact.

Impact Dashboard Reference:
Similar tests on ASINs with 10%+ CVR showed 72% success rate
(incremental revenue without organic cannibalization).
```

---

### 3.4 Signal 4: Harvest Cannibalization

**Purpose:** Detect when harvest campaigns improve efficiency but stall growth.

**Detection Logic:**

```sql
CREATE VIEW sc_analytics.signal_harvest_cannibalization AS
WITH harvest_performance AS (
    SELECT 
        report_date,
        SUM(CASE WHEN campaign_name LIKE '%harvest%' THEN sales END) as harvest_sales,
        SUM(CASE WHEN campaign_name LIKE '%harvest%' THEN spend END) as harvest_spend,
        SUM(CASE WHEN campaign_name LIKE '%harvest%' THEN sales END) / 
            NULLIF(SUM(CASE WHEN campaign_name LIKE '%harvest%' THEN spend END), 0) as harvest_roas
    FROM public.raw_search_term_data
    WHERE report_date >= CURRENT_DATE - 14
      AND client_id = 's2c_uae_test'
    GROUP BY report_date
),
discovery_performance AS (
    SELECT 
        report_date,
        SUM(CASE WHEN match_type IN ('BROAD', 'AUTO') THEN sales END) as discovery_sales
    FROM public.raw_search_term_data
    WHERE report_date >= CURRENT_DATE - 14
      AND client_id = 's2c_uae_test'
    GROUP BY report_date
)
SELECT 
    h.report_date,
    h.harvest_sales,
    h.harvest_roas,
    d.discovery_sales,
    a.total_ordered_revenue,
    -- Pattern: harvest ROAS improving + total revenue flat
    CASE 
        WHEN h.harvest_roas > LAG(h.harvest_roas, 7) OVER w * 1.1
         AND a.total_ordered_revenue BETWEEN 
             LAG(a.total_ordered_revenue, 7) OVER w * 0.95
             AND LAG(a.total_ordered_revenue, 7) OVER w * 1.05
        THEN TRUE
        ELSE FALSE
    END as is_cannibalizing
FROM harvest_performance h
JOIN discovery_performance d USING (report_date)
JOIN sc_analytics.account_daily a USING (report_date)
WINDOW w AS (ORDER BY h.report_date);
```

**Alert Trigger:**  
`is_cannibalizing = TRUE` for 5+ consecutive days

**UI Output:**

```
⚠️ Harvest Efficiency Improving, Total Revenue Flat

Severity: Medium
Duration: 7 days
Confidence: 82%

Metrics:
• Harvest ROAS: +18% (2.1 → 2.5)
• Discovery Spend: Stable
• Total Account Revenue: +2% (essentially flat)

Diagnosis:
Harvest campaigns are successfully isolating exact match traffic
at better ROAS, but you're not finding NEW traffic to replace it.
This is efficiency optimization without growth.

Action Required:
→ Expand discovery budget +20% to find new converting traffic
→ Test new broad match keywords in existing product categories
→ Launch Product Targeting campaigns to capture competitor ASINs

Goal: Grow the top of the funnel so harvest has more to harvest.

Impact Dashboard Reference:
Discovery campaigns historically show 14-day payback at 1.8 ROAS.
Short-term efficiency hit is offset by long-term harvest gains.
```

---

### 3.5 Signal 5: Over-Negation

**Purpose:** Detect when negative keywords are cutting volume without efficiency gains.

**Detection Logic:**

```sql
CREATE VIEW sc_analytics.signal_over_negation AS
WITH daily_metrics AS (
    SELECT 
        report_date,
        SUM(impressions) as total_impressions,
        SUM(clicks) as total_clicks,
        SUM(spend) as total_spend,
        SUM(sales) as total_sales,
        SUM(orders) as total_orders
    FROM public.raw_search_term_data
    WHERE report_date >= CURRENT_DATE - 14
      AND client_id = 's2c_uae_test'
    GROUP BY report_date
)
SELECT 
    report_date,
    total_impressions,
    total_clicks / NULLIF(total_impressions, 0) * 100 as ctr,
    total_orders / NULLIF(total_clicks, 0) * 100 as cvr,
    total_sales / NULLIF(total_spend, 0) as roas,
    total_sales,
    -- Pattern: impressions down + quality metrics stable/up + revenue down
    CASE 
        WHEN total_impressions < LAG(total_impressions, 7) OVER w * 0.8
         AND (total_clicks / NULLIF(total_impressions, 0)) >= 
             LAG(total_clicks / NULLIF(total_impressions, 0), 7) OVER w
         AND (total_sales / NULLIF(total_spend, 0)) > 
             LAG(total_sales / NULLIF(total_spend, 0), 7) OVER w
         AND total_sales < LAG(total_sales, 7) OVER w * 0.9
        THEN TRUE
        ELSE FALSE
    END as is_over_negated
FROM daily_metrics
WINDOW w AS (ORDER BY report_date);
```

**Alert Trigger:**  
`is_over_negated = TRUE` for 3+ consecutive days

**UI Output:**

```
⚠️ Traffic Volume Declining Despite Good Efficiency

Severity: Medium
Duration: 7 days
Confidence: 76%

Metrics:
• Impressions: -24% (12k → 9k/day)
• CTR: +5% (improving)
• CVR: Stable at 3.1%
• ROAS: +8% (improving)
• Revenue: -12% (declining)

Diagnosis:
You've cut search terms aggressively — traffic quality is excellent
but total volume is down. Efficiency improved at the cost of scale.

Action Required:
→ Audit negative keywords added in last 30 days
→ Identify negatives that cut >100 impressions/week
→ Selectively remove negatives where:
  - Original search term had ROAS >1.5
  - Volume was meaningful (>20 clicks/week)
→ Re-enable in phases, monitor impact

Goal: Restore volume without sacrificing efficiency gains.

Impact Dashboard Reference:
Negative removal tests historically show 60% restore profitable
volume, 40% confirm the negative was correct. Worth testing.
```

---

## 4. User Interface

### 4.1 Navigation

**Revised Tab Structure:**

```
SADDL App
├── Campaigns (existing)
├── Targets (existing)
├── Impact Dashboard (existing — shows optimization validation)
├── [NEW] Diagnostics
│   ├── Overview
│   ├── Signals
│   └── Trends
```

**Removed:**
- ~~Optimization Validation~~ (already in Impact Dashboard)

---

### 4.2 Page: Overview

**Purpose:** Executive summary of account health with root cause diagnosis.

**Layout:** (Same as original PRD)

```
┌────────────────────────────────────────────────────────────────┐
│  Diagnostics / Overview                                         │
├────────────────────────────────────────────────────────────────┤
│  ┌──────────┬──────────┬──────────┬──────────────────────────┐ │
│  │ TACOS    │ Organic %│ Revenue  │ Status                   │ │
│  │ 28.2%    │  58.1%   │ 4,289 AED│ 🟡 Demand Soft           │ │
│  │ ↗ +2.1pts│ ↘ -3.2pts│ ↘ -8%    │                          │ │
│  └──────────┴──────────┴──────────┴──────────────────────────┘ │
│                                                                 │
│  Root Cause Analysis (Last 7 Days)                             │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ 🔴 Market Demand Contraction (High Confidence)             ││
│  │    Evidence: Organic CVR -11%, Ad CVR -9%, CPC stable      ││
│  │    Impact: -12% total revenue                              ││
│  │    → NOT a PPC problem — your optimizations are working    ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ 🟡 Organic Rank Decay — 3 ASINs (Medium)                   ││
│  │    Top ASIN: B0DSFZK5W7 (-22% sessions, BSR +5.7k)        ││
│  │    Impact: -180 AED/day revenue                            ││
│  │    → Recommendation: Launch defense campaigns              ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Quick Links:                                                   │
│  [View All Signals →] [Impact Dashboard →] [Trends Analysis →] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**New Feature — Impact Dashboard Integration:**

```
┌────────────────────────────────────────────────────────────────┐
│  Recent Optimizations Context                                   │
├────────────────────────────────────────────────────────────────┤
│  Last 7 days: 8 actions validated                              │
│  Win Rate: 88% (7/8 outperformed market)                       │
│  Avg Impact: +14pts ROAS vs baseline                           │
│                                                                 │
│  Interpretation:                                                │
│  Your optimizations ARE working. The ROAS decline is driven    │
│  by external demand contraction, not failed optimization.      │
│                                                                 │
│  [View Details in Impact Dashboard →]                          │
└─────────────────────────────────────────────────────────────────┘
```

**Data Source:**  
Queries existing Impact Dashboard tables to pull recent win rate and show it in context with the diagnostic signals.

---

### 4.3 Page: Signals

**Purpose:** All active opportunity alerts with recommendations.

**Layout:** (Same as original PRD but without validation tab reference)

Signal cards show same structure, but "Impact Dashboard Reference" section at bottom links to relevant validations.

---

### 4.4 Page: Trends

**Purpose:** Multi-metric time series correlation analysis.

**Charts:**
1. Revenue Breakdown (stacked area: organic vs paid)
2. TACOS vs Organic Share (dual axis line)
3. CVR Comparison (organic vs paid line chart)
4. BSR Trend for Top 5 ASINs
5. Correlation Matrix

**NEW — DuPont ROAS Decomposition Widget:**

```
┌────────────────────────────────────────────────────────────────┐
│  ROAS Decomposition (Last 7 Days)                              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ROAS = (CVR × AOV) / CPC                                      │
│                                                                 │
│  ┌──────────────┬──────────┬──────────┬──────────────────────┐│
│  │ Metric       │ Current  │ 7d Ago   │ Change   │ Impact   ││
│  ├──────────────┼──────────┼──────────┼──────────┼──────────┤│
│  │ CVR          │  2.8%    │  3.1%    │  -9.7%   │ Primary  ││
│  │ AOV          │  42 AED  │  41 AED  │  +2.4%   │ Neutral  ││
│  │ CPC          │  1.85    │  1.82    │  +1.6%   │ Neutral  ││
│  ├──────────────┼──────────┼──────────┼──────────┼──────────┤│
│  │ ROAS         │  1.92    │  2.15    │  -10.7%  │          ││
│  └──────────────┴──────────┴──────────┴──────────┴──────────┘│
│                                                                 │
│  Primary Driver: CVR decline (-9.7%)                           │
│  Diagnosis: This is a product/market problem, not PPC.         │
│                                                                 │
│  Root Cause Options:                                            │
│  • Demand softness (check organic CVR — if also down, market)  │
│  • Traffic quality shift (check impression share by match type)│
│  • Listing issue (check A+ content, images, reviews)           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Integration with Impact Dashboard

### 5.1 Data Access

**Read-Only Access to Impact Dashboard Tables:**

```python
# utils/impact_dashboard.py
def get_recent_validation_summary(days: int = 7) -> dict:
    """
    Pull recent optimization results from Impact Dashboard.
    Returns summary stats for context in diagnostic views.
    """
    query = """
    SELECT 
        COUNT(*) as total_actions,
        COUNT(*) FILTER (WHERE status = 'WIN') as wins,
        AVG(impact_pts) as avg_impact
    FROM [impact_dashboard_table]  -- Replace with actual table name
    WHERE action_date >= CURRENT_DATE - %s
    """
    # Execute and return
```

**Usage in Diagnostics:**

```python
# pages/diagnostics_overview.py
validation_context = get_recent_validation_summary(days=7)

st.markdown(f"""
### Optimization Performance Context

Recent validations show **{validation_context['win_rate']:.0f}% win rate**
with average **+{validation_context['avg_impact']:.1f}pts impact**.

This confirms your optimizations are effective. Current ROAS decline
is driven by external factors identified in signals above.

[View detailed validation in Impact Dashboard →]
""")
```

### 5.2 Cross-Linking

Every signal card includes:

```
Impact Dashboard Reference:
[Link to related validations that validate the recommendation]
```

Example:
```
Impact Dashboard Reference:
Previous brand defense campaigns for this ASIN type showed +28pts ROAS
vs market baseline in 4/5 validations, confirming this approach works.
[View brand defense validations →]
```

**Implementation:**
- Links use existing Impact Dashboard deep-link URLs
- Signals reference validation patterns by action type, not specific events
- Diagnostic tool READS from Impact Dashboard, never WRITES

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
- BSR pipeline (`pipeline/bsr_pipeline.py`)
- `sc_raw.bsr_history` table populated with 90 days backfill
- `sc_analytics.bsr_trends` view
- Integration layer to read from Impact Dashboard tables

**Validation:**
- BSR data for all active ASINs present
- BSR trends view returns expected results
- Impact Dashboard summary query works

---

### Phase 2: Signal Detection (Week 3-4)

**Deliverables:**
- All 5 signal detection views
- Signal detection functions in `utils/diagnostics.py`
- Overview page in Streamlit
- Signals page in Streamlit

**Validation:**
- All signals correctly detect known patterns in historical data
- Signal severity classification works
- Integration with Impact Dashboard shows correct context

---

### Phase 3: Trends & Analytics (Week 5-6)

**Deliverables:**
- Trends page with all 4 core charts
- DuPont ROAS decomposition widget
- Correlation matrix computation
- PDF report export

**Validation:**
- All charts render correctly with real data
- Correlation matrix shows expected relationships
- Export generates readable PDF

---

## 7. Success Metrics

**Product Performance:**
- Signal accuracy: >80% of HIGH severity signals result in user action
- False positive rate: <15% of signals dismissed as irrelevant
- User engagement: Diagnostic tab visited >3x/week per active user

**Business Impact:**
- Root cause identification: Users correctly identify market vs PPC issues >90% of time
- TACOS volatility: Reduced 25% (measured as 30-day rolling std dev)
- User retention: +15% among users who actively use diagnostic tab

**Integration:**
- Impact Dashboard cross-link click-through: >40%
- Users report diagnostics + validation together improve confidence in decisions

---

## 8. Removed Scope (Already Exists)

**The following were in original PRD but are now OUT OF SCOPE:**

❌ `sc_analytics.optimization_events` table  
❌ Event logger (`pipeline/event_logger.py`)  
❌ Validation scheduler  
❌ Optimization Validation page  
❌ Validation views (`optimization_validation_summary`, `validation_by_action_type`)  
❌ Win rate tracking  
❌ Counterfactual analysis (already in Impact Dashboard)

**Why removed:**  
These capabilities already exist in the Impact Dashboard. Diagnostic tool focuses purely on **root cause analysis and opportunity identification**, leveraging Impact Dashboard for validation context.

---

*Diagnostic Intelligence Layer PRD v2.0 — focused, integrated, production-ready.*
