# SADDL AdPulse — Demand-Adjusted Optimization (DAO) Module
## Product Requirements Document v1.0

**Status:** Draft for Internal Review  
**Author:** SADDL Product  
**Date:** February 2026  
**Scope:** New Module — Demand Signal Layer + Spend Envelope Engine

---

## 1. Overview

### 1.1 Problem Statement

Current Amazon PPC optimization tools — including the existing SADDL AdPulse bid optimization layer — treat spend as an independent variable and optimize bids within it. This creates a structural failure mode: when external demand contracts (seasonality, competitor pricing shifts, category softness), spend does not contract proportionally, causing ACOS/ROAS to deteriorate regardless of how well bids are optimized.

The core issue is not bid quality. It is the absence of a feedback loop between external demand signals and spend velocity.

### 1.2 Solution Framing

The Demand-Adjusted Optimization (DAO) module introduces a **three-layer architecture** upstream of the existing bid optimization engine:

1. **Demand Signal Layer** — measures external and internal demand using a composite index
2. **Spend Envelope Engine** — dynamically sets the maximum allowable spend per campaign tier based on the demand index
3. **Health Decomposition Engine** — decomposes efficiency changes into root causes, routing each to the correct optimization response

The client-facing promise: *efficiency (ACOS/ROAS) is defended regardless of market conditions, because spend always tracks demand.*

### 1.3 Strategic Differentiation

Every existing tool (Perpetua, Scale Insights, Pacvue, Helium 10 Adtomic) optimizes *what to bid*. DAO is the first system that optimizes *whether to bid at all, and how much*, based on real demand signals. This is the operational definition of Decision-First PPC.

---

## 2. Module Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                         │
│  Ad Console API  │  Seller Central API  │  Brand Analytics  │ Manual │
└────────────┬────────────────┬──────────────────┬──────────────┬─────┘
             │                │                  │              │
             ▼                ▼                  ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DEMAND SIGNAL LAYER                            │
│   Impression Index │ CVR Index │ Organic Share Index │ BSR Index   │
│                    └──────────┬──────────────────────┘             │
│                    COMPOSITE DEMAND INDEX (CDI)                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   HEALTH DECOMPOSITION ENGINE                        │
│   DuPont Decomposition │ Issue Classifier │ Action Router           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SPEND ENVELOPE ENGINE                           │
│   Envelope Calculator │ Campaign Tier Allocator │ Circuit Breakers  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│               EXISTING BID OPTIMIZATION LAYER (SADDL)               │
│   Target-level bid decisions operate within approved spend envelope │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Requirements

### 3.1 Ad Console Inputs (Existing — Already Accessible)

| Metric | Granularity | Frequency | Usage |
|---|---|---|---|
| Impressions | Campaign / Ad Group / Target | Daily | Demand proxy; auction volume signal |
| Clicks | Campaign / Ad Group / Target | Daily | Traffic volume |
| Spend | Campaign / Ad Group / Target | Daily | Spend velocity tracking |
| Sales (attributed) | Campaign / Ad Group / Target | Daily | Revenue signal |
| Orders (attributed) | Campaign / Ad Group / Target | Daily | Conversion count |
| ACOS | Campaign | Daily | Efficiency tracking |
| CPC | Campaign / Target | Daily | Cost input for DuPont |
| CTR | Campaign / Target | Daily | Traffic quality proxy |
| Match type | Target level | Static | Campaign tier classification |
| Campaign type | Auto / SP / SD / SB | Static | Tier classification |

**Derived from ad console (computed in SADDL):**
- CVR = Orders / Clicks (by campaign and account level)
- ROAS = Sales / Spend
- Impression share trend (week-over-week, normalized)

### 3.2 Seller Central Inputs (New Integration Required)

| Metric | Report Name | Frequency | Usage |
|---|---|---|---|
| Total ordered revenue (all channels) | Business Report — ASIN level | Daily | TACOS calculation; organic share |
| Total ordered units | Business Report — ASIN level | Daily | Unit economics |
| Best Seller Rank (BSR) | ASIN detail page / API | Weekly minimum | Product demand health |
| Organic sessions | Business Report | Daily | Organic traffic signal |
| Buy Box % | Business Report | Daily | Listing competitiveness |
| Session-to-unit conversion rate | Business Report | Daily | Product-level CVR (organic) |

**Derived from Seller Central:**
- TACOS = Total Ad Spend / Total Ordered Revenue
- Organic Sales Share = (Total Revenue − Ad-Attributed Revenue) / Total Revenue
- Ad Dependency Ratio = Ad-Attributed Revenue / Total Revenue (inverse of above)
- BSR Week-over-Week Delta

### 3.3 Optional External Inputs (Phased — Phase 2+)

| Signal | Source | Integration Type | Priority |
|---|---|---|---|
| Category keyword search volume | Helium 10 / Brand Analytics | API / Manual upload | High |
| Competitor price index (top 3 ASINs) | Manual input / scrape | Weekly manual | Medium |
| Category BSR benchmark | Manual observation | Weekly manual | Medium |
| Seasonal index (historical baseline) | Internal — derived from 52-week history | Computed | High |

---

## 4. Computed Indices

### 4.1 Impression Trend Index (ITI)

**Purpose:** Measures whether auction volume (available demand) is growing, stable, or contracting.

**Formula:**
```
ITI = (Impressions_current_7d / Impressions_baseline_7d) × 100

Where:
  baseline_7d = same 7-day period, 4 weeks prior (controls for day-of-week effects)
  Normalization: 100 = baseline; >100 = expanding demand; <100 = contracting
```

**Thresholds:**
- ITI ≥ 110: Expanding — allow spend envelope to increase
- ITI 90–110: Stable — hold spend envelope
- ITI 75–90: Soft decline — reduce discovery spend 10–20%
- ITI < 75: Material contraction — circuit breaker triggers

**Data source:** Ad console impressions, campaign level, aggregated to account  
**Update frequency:** Daily  
**Lookback:** Rolling 7-day vs. same period 4 weeks prior

---

### 4.2 Conversion Rate Index (CRI)

**Purpose:** Distinguishes between traffic quality problems (match type / targeting) and product-demand problems (CVR declining uniformly).

**Formula:**
```
CRI_exact = CVR_exact_7d / CVR_exact_baseline_7d × 100
CRI_broad = CVR_broad_7d / CVR_broad_baseline_7d × 100
CRI_auto  = CVR_auto_7d  / CVR_auto_baseline_7d  × 100

Composite CRI = weighted average:
  CRI = (CRI_exact × 0.5) + (CRI_broad × 0.3) + (CRI_auto × 0.2)
```

**Interpretation logic:**
- CRI_exact stable, CRI_broad/auto declining → traffic quality problem (targeting/negation issue)
- All CRI indices declining uniformly → product/market demand problem
- CRI declining + ITI declining → compound demand contraction, highest severity

**Data source:** Ad console clicks and orders, by campaign type  
**Update frequency:** Daily (7-day rolling)  
**Minimum data threshold:** 30 clicks per match type per 7-day window before index is considered valid

---

### 4.3 Organic Share Index (OSI)

**Purpose:** Detects organic rank decay — the condition where ad conversions are replacing organic conversions that previously came free, creating rising TACOS even with stable ad ROAS.

**Formula:**
```
OSI = Organic_Sales_7d / Total_Sales_7d × 100

Where:
  Organic Sales = Total Ordered Revenue (Seller Central) − Ad-Attributed Sales (Ad Console)
  
OSI_delta = OSI_current − OSI_baseline (same period 4 weeks prior)
```

**Thresholds:**
- OSI_delta > 0: Organic share growing (healthy, ads supplementing organic)
- OSI_delta 0 to −5: Slight organic erosion — monitor
- OSI_delta −5 to −15: Material organic decay — flag for listing/rank review
- OSI_delta < −15: Severe organic dependency shift — escalate outside PPC scope

**Data source:** Seller Central Business Report (total revenue) + Ad Console (attributed revenue)  
**Update frequency:** Weekly (daily data, 7-day rolling aggregation)  
**Limitation:** Attribution overlap exists; Amazon's 7-day and 14-day attribution windows can cause double-counting. Apply 10% correction factor to attributed sales before computing organic share.

---

### 4.4 BSR Health Index (BHI)

**Purpose:** Measures total product demand momentum (organic + paid combined) as a lagging confirmation signal.

**Formula:**
```
BHI = (BSR_baseline / BSR_current) × 100

Note: Lower BSR = better rank, so this formula ensures BHI > 100 means rank improving.

BSR_baseline = 4-week average BSR for the SKU
BSR_current  = current week average BSR
```

**Thresholds:**
- BHI ≥ 105: Rank improving — product demand healthy
- BHI 95–105: Stable
- BHI 80–95: Rank softening — investigate
- BHI < 80: Rank deteriorating materially — product-level issue confirmed

**Data source:** Seller Central product detail / API, or manual weekly input  
**Update frequency:** Weekly  
**Scope:** Top 5 revenue-generating ASINs minimum; all active ASINs ideally

---

### 4.5 Composite Demand Index (CDI)

**Purpose:** Single index that summarizes overall demand health for the account, used as the primary input to the Spend Envelope Engine.

**Formula:**
```
CDI = (ITI × 0.35) + (CRI × 0.35) + (OSI_normalized × 0.20) + (BHI_normalized × 0.10)

Where:
  OSI_normalized = (OSI / OSI_baseline) × 100
  BHI_normalized = BHI (already indexed to 100)

Weights rationale:
  ITI and CRI are highest-frequency, most actionable signals (0.35 each)
  OSI captures organic health — important but lags (0.20)
  BHI is a lagging confirmation signal only (0.10)
```

**Output range:** Indexed to 100 (baseline). Interpretive bands:

| CDI Range | Demand State | Spend Envelope Action |
|---|---|---|
| ≥ 115 | Expanding demand | Expand envelope +15% |
| 105–115 | Moderate growth | Expand envelope +5–10% |
| 95–105 | Stable | Hold envelope |
| 85–95 | Soft decline | Contract envelope −10–15% |
| 75–85 | Moderate decline | Contract envelope −20–25% |
| < 75 | Severe contraction | Circuit breaker — reduce to maintenance spend |

**Update frequency:** Daily recompute (inputs permitting)  
**Fallback logic:** If any single index lacks sufficient data, CDI is computed from available indices with renormalized weights. If fewer than 2 indices are available, CDI is flagged as unreliable and envelope holds at last valid state.

---

## 5. Health Decomposition Engine

### 5.1 DuPont ROAS Decomposition

Every ROAS change is mathematically decomposable into three and only three factors:

```
ROAS = (CVR × AOV) / CPC

ROAS_delta = f(CVR_delta, AOV_delta, CPC_delta)

Contribution analysis:
  CVR contribution  = (CVR_t1 / CVR_t0 − 1) × ROAS_t0 × (AOV_t0 / CPC_t0)
  AOV contribution  = (AOV_t1 / AOV_t0 − 1) × ROAS_t0 × (CVR_t0 / CPC_t0) [simplified]
  CPC contribution  = −(CPC_t1 / CPC_t0 − 1) × ROAS_t0
```

This decomposition runs weekly for each campaign tier and at account level. Output surfaces as a waterfall chart in the UI showing each lever's contribution to the ROAS change in the period.

### 5.2 Issue Classification Matrix

| CVR Trend | CPC Trend | Impression Trend | OSI Trend | Classification | Routing |
|---|---|---|---|---|---|
| Declining (uniform) | Stable | Declining | Declining | External demand contraction | Spend envelope reduction |
| Declining (uniform) | Stable | Stable | Declining | Organic rank decay | Flag outside PPC + defend rank via spend |
| Declining (broad/auto only) | Stable | Stable | Stable | Traffic quality degradation | Targeting/negation audit |
| Stable | Rising | Stable | Stable | Competitive bid pressure | CPC defense — evaluate bid floors |
| Declining | Rising | Declining | Declining | Compound market deterioration | Maximum severity — circuit breaker |
| Stable | Stable | Stable | Declining | Organic-to-paid shift creeping | OSI alert — monitor |
| Improving | Stable | Improving | Stable | Demand expansion | Envelope expansion |

### 5.3 Action Routing Logic

Each classification produces one of four routing outcomes:

**Route A — Within PPC Scope, Bid Action**
Trigger: CPC rising, CVR stable. Action: bid adjustment recommendations passed to existing optimization layer.

**Route B — Within PPC Scope, Structural Action**
Trigger: CVR degraded on broad/auto but not exact. Action: targeting audit, negation review, match type reallocation.

**Route C — Spend Envelope Action**
Trigger: CDI declining, demand contraction confirmed. Action: spend envelope contracts per CDI bands. Bid layer operates within new envelope.

**Route D — Outside PPC Scope, Escalation**
Trigger: OSI delta severe, BHI declining, CVR uniform decline despite spend reduction. Action: system flags as product/market issue. Recommendation displayed: "Current efficiency decline is not addressable through PPC optimization. Recommended actions: [pricing review / listing audit / inventory check / BSR recovery strategy]." PPC spend reduced to maintenance floor to avoid wasting budget during product-level issues.

---

## 6. Spend Envelope Engine

### 6.1 Campaign Tier Classification

All active campaigns are classified into tiers that receive differential envelope treatment:

| Tier | Campaign Types | Role | Envelope Sensitivity |
|---|---|---|---|
| T1 — Discovery | Auto, Broad match | Demand capture, harvest feed | High — contracts first in decline |
| T2 — Harvest Pipeline | Recent harvested targets (<90 days), still proving | Volume at acceptable efficiency | Medium |
| T3 — Proven Performers | Exact match harvested, >90 days, ROAS above target | Core revenue defense | Low — protected in decline |
| T4 — Brand Defense | Brand keyword exact match | Brand protection | Minimal — near-static |
| T5 — Rank Defense | Specific high-value targets for BSR maintenance | Organic rank support | Contextual — expands during rank decay |

### 6.2 Envelope Calculation

```
Base Spend Envelope = Trailing 28-day average daily spend × 7 (weekly envelope)

CDI-Adjusted Envelope per tier:

  T1_envelope = Base_T1 × CDI_multiplier × T1_sensitivity_factor (1.5)
  T2_envelope = Base_T2 × CDI_multiplier × T2_sensitivity_factor (1.0)
  T3_envelope = Base_T3 × CDI_multiplier × T3_sensitivity_factor (0.4)
  T4_envelope = Base_T4 (static, no CDI adjustment)
  T5_envelope = Base_T5 × OSI_adjustment (expands when organic decays)

CDI_multiplier mapping:
  CDI ≥ 115  → 1.15
  CDI 105–115 → 1.05–1.10
  CDI 95–105  → 1.00
  CDI 85–95   → 0.85–0.90
  CDI 75–85   → 0.75
  CDI < 75    → 0.50 (maintenance floor)
```

### 6.3 Circuit Breakers

Independent of CDI, three circuit breakers trigger immediate spend envelope reduction:

**CB-1: Rapid ROAS Deterioration**
- Trigger: 7-day rolling ROAS drops >25% vs. 28-day baseline in less than 5 days
- Action: Freeze T1 spend, reduce T2 by 30%, alert user immediately
- Override: User must manually approve spend resumption

**CB-2: Spend-Revenue Divergence**
- Trigger: Spend growing while revenue declining for 5+ consecutive days (the pattern visible in your charts)
- Action: Cap T1 and T2 spend at current level, trigger Health Decomposition analysis
- Override: Auto-releases after CDI recovers above 95

**CB-3: CVR Floor Breach**
- Trigger: Account-level CVR drops below 50% of 90-day baseline
- Action: Reduce all non-T4 spend to 50% of envelope, escalate to Route D classification
- Override: Manual only

---

## 7. Views & UI Requirements

### 7.1 Demand Health Dashboard

**Purpose:** Single-screen summary of demand health status. Entry point for DAO module.

**Components:**

- **CDI Gauge** — large visual indicator showing current CDI value, trend arrow (7-day direction), and color band (green/yellow/orange/red). Displayed prominently at top of screen.
- **Index Breakdown Panel** — four sub-gauges showing ITI, CRI, OSI, BHI individually with their contribution weight and trend direction
- **Demand State Label** — plain-language status: "Demand Stable," "Soft Demand Decline," "Demand Contraction — Spend Envelope Active," etc.
- **Envelope Status Bar** — shows current approved spend envelope vs. baseline for each tier (T1–T5) as a % adjustment and absolute AED/USD value
- **Active Circuit Breakers** — badge count and list of any active CBs with trigger reason and timestamp

**Update cadence:** Daily refresh. Last updated timestamp visible.

---

### 7.2 Health Decomposition View

**Purpose:** Explains *why* efficiency changed. Answers the "what happened?" question before any action is taken.

**Components:**

- **ROAS Waterfall Chart** — period-over-period (selectable: WoW, MoM, custom) showing CVR contribution, AOV contribution, CPC contribution to ROAS delta. Positive bars green, negative bars red.
- **Lever Detail Table** — for each lever: current value, baseline value, % change, and whether change is within normal variance band or statistically significant
- **Issue Classification Badge** — outputs from 5.2 matrix: "Traffic Quality Issue," "Demand Contraction," "Organic Rank Decay," etc.
- **Routing Outcome** — clearly labeled: Route A/B/C/D with plain-language explanation and recommended action
- **Match Type CVR Comparison** — side-by-side CVR trend for Exact / Broad / Auto. Visual divergence immediately surfaces traffic quality vs. demand problems.

---

### 7.3 Spend Envelope Management View

**Purpose:** Shows how the envelope is set and allows user override with audit trail.

**Components:**

- **Tier Envelope Table** — for each tier (T1–T5): baseline spend, CDI multiplier applied, current approved envelope, actual spend-to-date (current period), % consumed, projected weekly total
- **Envelope History Chart** — 12-week trend of approved envelope vs. actual spend vs. CDI. Shows how the system has been adjusting over time.
- **Override Controls** — user can manually adjust any tier's envelope with a reason code. All overrides logged with timestamp and reason. Override automatically expires after 7 days unless renewed.
- **Projection Panel** — given current CDI trajectory, projects spend envelope and estimated ROAS for next 7 and 14 days

---

### 7.4 Account Efficiency Decomposition View (Executive Summary)

**Purpose:** Client-facing view. Answers "how are we performing and why" in one screen. Designed for monthly review presentations.

**Components:**

- **Efficiency Defense Score** — proprietary metric: measures how well SADDL preserved efficiency relative to demand decline. Formula: `EDS = (ROAS_actual / ROAS_predicted_without_DAO) × 100`. If DAO held ROAS flat in a declining market, EDS = high. This is the proof-of-value metric.
- **Demand vs. Spend vs. Revenue Chart** — three-line chart showing CDI index, spend envelope, and revenue over the period. When working correctly, spend and CDI track together while revenue follows demand. This is the visual proof that spend tracked demand.
- **Attribution Adjustment Notice** — automatic disclosure when viewing recent periods: "Data for the last 14 days includes estimated attribution adjustment. Final numbers may vary ±8%."
- **Period Summary Table** — ACOS, ROAS, TACOS, Organic Share, CDI average for selected period vs. prior period vs. same period last year (when data available)

---

### 7.5 Notification & Alert System

| Alert Type | Trigger | Delivery | Urgency |
|---|---|---|---|
| CDI Drop Alert | CDI falls below 90 for 3 consecutive days | In-app + email | Medium |
| Circuit Breaker Fired | Any CB triggers | In-app + email + SMS option | High |
| Organic Decay Warning | OSI delta < −10 for 2 consecutive weeks | In-app + email | Medium |
| Envelope Override Expiry | User override approaching 7-day expiry | In-app | Low |
| Attribution Lag Notice | User views data within 14-day rolling window | In-app inline | Informational |
| Route D Escalation | Outside-PPC-scope issue classified | In-app + email | High |

---

## 8. Technical & Computation Requirements

### 8.1 Data Pipeline

- Ad console data: pulled via Amazon Advertising API, daily refresh at 06:00 account local time
- Seller Central data: pulled via SP-API (Selling Partner API), daily refresh
- All raw metrics stored at campaign/date granularity with 24-month retention
- Derived indices computed post-ingestion, stored in separate index table with full version history
- CDI historical series must be preserved — never overwritten — to enable backtesting

### 8.2 Minimum Data Requirements for Index Validity

| Index | Minimum Clicks/Impressions | Minimum History | Fallback Behavior |
|---|---|---|---|
| ITI | 500 impressions / 7 days | 4 weeks (for baseline) | Flag as insufficient; hold envelope |
| CRI | 30 clicks / 7 days per match type | 4 weeks | Exclude that match type from CRI; renormalize weights |
| OSI | Any revenue data | 4 weeks | Flag; exclude from CDI; BHI weight increases to 0.20 |
| BHI | N/A — rank data | 4 weeks BSR history | Flag; exclude from CDI |

### 8.3 Attribution Adjustment

Amazon's 14-day attribution window means data within the last 14 days systematically undercounts conversions. All CVR, ROAS, and OSI calculations must apply an adjustment factor:

```
Days since event:  1–3     4–7     8–14    15+
Adjustment factor: 0.65    0.80    0.92    1.00

Applied as: Adjusted_orders = Raw_orders / adjustment_factor
```

Adjustment factors should be calibrated against account-specific historical lag data after 90 days of operation.

### 8.4 Statistical Significance Thresholds

Index movements should only trigger action when they exceed noise:

- Index changes < 5 points: Display only, no action
- Index changes 5–10 points persisting < 3 days: Alert only, no envelope change
- Index changes 5–10 points persisting ≥ 3 days: Envelope adjustment
- Index changes > 10 points: Immediate envelope adjustment on day 1

Variance bands for each index should be computed from trailing 12-week standard deviation and displayed on all charts.

---

## 9. Phased Implementation Plan

### Phase 1 — Foundation (Weeks 1–6)
- Implement Seller Central SP-API integration for Business Report data
- Build ITI and CRI indices (ad console data only — already available)
- Build Health Decomposition Engine (DuPont decomposition + issue classification)
- Build basic Spend Envelope Engine for T1/T2 campaigns only
- Deploy Health Decomposition View and Spend Envelope Management View

**Deliverable:** Clients can see *why* ROAS is changing (decomposition) and SADDL automatically contracts T1/T2 spend when CRI or ITI decline materially.

### Phase 2 — Full Demand Signal Layer (Weeks 7–12)
- Add OSI calculation (requires Seller Central integration from Phase 1)
- Add BHI (BSR data — Seller Central or manual upload)
- Compute full CDI
- Build Demand Health Dashboard
- Implement Circuit Breakers CB-1 and CB-2
- Activate T3–T5 envelope management

**Deliverable:** Full CDI operational. All five campaign tiers under envelope management. Executive summary view live.

### Phase 3 — External Signals + Automation (Weeks 13–20)
- Add Brand Analytics / Helium 10 keyword volume integration (optional, customer-permissioned)
- Implement CB-3
- Build Efficiency Defense Score and back-calculate for existing accounts
- Add attribution adjustment calibration engine (account-specific lag factors)
- Build Route D escalation flow with specific outside-PPC recommendations

**Deliverable:** Full DAO module operational. EDS becomes primary proof-of-value metric for customer retention and sales materials.

---

## 10. Success Metrics

### Product Performance KPIs
- ACOS variance vs. baseline during demand-declining periods: target <5% deterioration when CDI drops 10–15%
- False positive rate on circuit breakers: target <10% (CB fires that didn't correspond to real demand decline)
- Efficiency Defense Score: target average EDS ≥ 110 across active accounts in declining demand periods

### Adoption KPIs
- % of accounts with Seller Central integration connected: target 80% within 60 days of Phase 1 launch
- Dashboard daily active view rate: target ≥ 3x weekly per account manager
- Circuit breaker override rate: target <20% (high override = users don't trust the system)

---

## 11. Open Questions & Risks

| Item | Description | Owner | Priority |
|---|---|---|---|
| SP-API access | Does each agency partner need separate SP-API credentials? What is the authorization flow? | Engineering | High |
| BSR data freshness | BSR changes hourly on Amazon; weekly manual input may lag. Explore automated scrape. | Product | Medium |
| Multi-ASIN attribution | For accounts with 50+ ASINs, OSI computation across SKUs needs aggregation logic. Define rollup rules. | Engineering | High |
| Seasonal baseline | First-year accounts have no same-period-prior-year baseline. Define fallback (category index or category-matched cohort baseline). | Data | Medium |
| Client transparency | How much of the CDI and routing logic is exposed to end clients vs. account managers only? | Product | Medium |
| AED vs. USD normalization | GCC accounts report in AED; normalize all absolute thresholds to % of account spend, not fixed currency amounts. | Engineering | Low |

---

*Document version 1.0. Next review scheduled upon Phase 1 build initiation.*
