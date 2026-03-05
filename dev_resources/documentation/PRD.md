# PPC Optimizer - Product Requirements Document (PRD)

**Version**: 2.2  
**Last Updated**: February 20, 2026  
**Document Owner**: Zayaan Yousuf

---

## Executive Summary

PPC Optimizer is a comprehensive Amazon Advertising optimization platform that automates the analysis, optimization, and management of Sponsored Products campaigns. The system ingests performance data, identifies optimization opportunities, generates actionable recommendations, and tracks the impact of implemented changes.

---

## Product Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PPC OPTIMIZER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────────┐    ┌────────────────────────────┐  │
│  │   DATA      │ => │   PERFORMANCE   │ => │       OPTIMIZER            │  │
│  │   INPUT     │    │   REPORTING     │    │  ┌──────────────────────┐  │  │
│  │   MODEL     │    │   MODEL         │    │  │ Harvest Module       │  │  │
│  └─────────────┘    └─────────────────┘    │  │ Negative Module      │  │  │
│                                             │  │ Bid Optimizer        │  │  │
│       ┌─────────────────────────────────┐  │  │ Campaign Launcher    │  │  │
│       │        IMPACT MODEL             │  │  │ Bulk Export          │  │  │
│       │  (Before/After Measurement)     │  │  └──────────────────────┘  │  │
│       └─────────────────────────────────┘  └────────────────────────────┘  │
│                                                                              │
│       ┌─────────────────────────────────┐                                   │
│       │       FORECAST MODEL            │                                   │
│       │   (Simulation & Projections)    │                                   │
│       └─────────────────────────────────┘                                   │
│                                                                              │
│       ┌─────────────────────────────────┐                                   │
│       │      ONBOARDING SYSTEM          │                                   │
│       │   (Wizard, Empty States)        │                                   │
│       └─────────────────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Data Input Model

### 1.1 Overview
The Data Input Model is the foundation of the system. It handles ingestion, validation, normalization, and persistence of all input data required for optimization.

### 1.2 Data Sources

| Data Source | Required | Description | Key Columns |
|-------------|----------|-------------|-------------|
| **Search Term Report** | ✅ Required | Primary performance data from Amazon Advertising | Campaign Name, Ad Group Name, Customer Search Term, Targeting, Match Type, Spend, Sales, Clicks, Impressions, Orders |
| **Advertised Product Report** | Optional | Maps campaigns/ad groups to SKUs and ASINs | Campaign Name, Ad Group Name, SKU, ASIN |
| **Bulk ID Mapping** | Optional | Amazon bulk file with Campaign IDs, Ad Group IDs, Keyword IDs | Entity, Campaign Id, Ad Group Id, Keyword Id, Product Targeting Id |
| **Category Mapping** | Optional | Internal SKU to Category/Sub-Category mapping | SKU, Category, Sub-Category |

### 1.3 Data Processing Pipeline

```
Raw File Upload
      │
      ▼
┌─────────────────────┐
│  Column Detection   │ ← SmartMapper identifies columns automatically
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Column Normalization │ ← Map to standard schema (Campaign Name, Spend, etc.)
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Data Type Casting  │ ← Ensure numeric types for metrics
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Match Type Inference │ ← Detect AUTO/PT/CATEGORY from targeting expressions
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Data Enrichment    │ ← Merge bulk IDs, SKUs, categories
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Database Persistence │ ← Save aggregated data to PostgreSQL
└─────────────────────┘
```

### 1.4 Data Aggregation Rules

Data is aggregated at the **Campaign + Ad Group + Target + Week** level:
- Daily rows are summed into weekly aggregates
- Metrics aggregated: Spend, Sales, Clicks, Impressions, Orders
- Week defined as Monday-Sunday (ISO week format)

### 1.5 Database Schema

**Primary table: `target_stats`**
| Column | Type | Description |
|--------|------|-------------|
| client_id | VARCHAR | Account identifier |
| start_date | DATE | Week start date (Monday) |
| campaign_name | VARCHAR | Campaign name (normalized) |
| ad_group_name | VARCHAR | Ad Group name (normalized) |
| target_text | VARCHAR | Targeting expression or keyword |
| match_type | VARCHAR | exact/broad/phrase/auto/pt/category |
| spend | DECIMAL | Total spend for period |
| sales | DECIMAL | Total sales for period |
| clicks | INTEGER | Total clicks for period |
| impressions | INTEGER | Total impressions for period |
| orders | INTEGER | Total orders for period |

### 1.6 Target Grouping and Identification (CANONICAL REFERENCE)

> **CRITICAL**: This section defines the grouping and identification logic used throughout the entire codebase. Reference this whenever implementing action logging, impact calculation, or optimization logic.

#### 1.6.1 Universal Grouping Key

**All actions and performance data are grouped by:**
```
Campaign Name + Ad Group Name + Target (Keyword/PT/ASIN/Auto Type)
```

This applies to:
- Action logging
- Impact measurement
- Bid optimization
- Performance aggregation

#### 1.6.2 Target Type Identification

| Target Type | Identification Pattern | Example |
|-------------|------------------------|---------|
| **Category** | `category="..."` | `category="brahmi" price>149` |
| **Product Targeting (PT)** | `asin="B0XXXXXXX"` or `asin-expanded="B0XXXXXXX"` | `asin="B08TT9LR1W"` |
| **Auto** | `close-match`, `loose-match`, `complements`, `substitutes` | `close-match` |
| **Keyword (Exact)** | match_type = `exact` | `moss stick` (exact) |
| **Keyword (Phrase)** | match_type = `phrase` | `moss stick` (phrase) |
| **Keyword (Broad)** | match_type = `broad` | `moss stick` (broad) |

#### 1.6.3 Customer Search Term (CST) Usage

**CST is ONLY used for:**
- Identifying harvest candidates (search terms to graduate to Exact match)
- Identifying negative candidates (search terms to block)

**CST is NOT used for:**
- Grouping keys
- Impact calculation joins
- Bid optimization grouping

#### 1.6.4 Impact Calculation Joins

When matching actions to performance data in `target_stats`:

```sql
-- Correct: Join on Campaign + Ad Group
ON LOWER(action.campaign_name) = LOWER(stats.campaign_name)
AND LOWER(action.ad_group_name) = LOWER(stats.ad_group_name)

-- Wrong: Join on target_text (only 10% match rate)
ON LOWER(action.target_text) = LOWER(stats.target_text)
```

**Performance data is aggregated at the Ad Group level** to capture all search term activity affected by the action.

---

## 2. Performance Reporting Model

### 2.1 Overview
The Performance Reporting Model provides comprehensive dashboards for analyzing campaign performance, identifying trends, and understanding performance distribution by various dimensions.

### 2.2 Key Features

### 2.2 Key Features

#### 2.2.1 Executive Dashboard (New - Jan 2025)
A high-level command center for account health and strategic decision-making.

**A. KPI Cards (Gradient Style)**
- **Total Spend**: With month-to-date pacing
- **Total Sales**: Attributed revenue
- **ROAS**: Return on Ad Spend (with color-coded delta)
- **Net Decision Impact**: Cumulative value of optimization actions

**B. Strategic Gauges (4-Zone Color System)**
- **Account Health**: Composite score (0-100)
- **Decision ROI**: Net Decision Impact / Managed Spend (Target: >5%)
- **Spend Efficiency**: % of spend in "efficient" ad groups (ROAS > 2.0x)
- *Zones*: Poor (Rose) → Fair (Amber) → Good (Teal) → Excellent (Emerald)

**C. Visualizations**
- **Performance Quadrants (Scatter)**: Campaigns mapped by ROAS vs. CVR.
    - *Stars*: High ROAS, High CVR (Emerald)
    - *Scale Potential*: High ROAS, Low CVR (Amber)
    - *Profit Potential*: Low ROAS, High CVR (Cyan)
    - *Cut*: Low ROAS, Low CVR (Rose)
- **Revenue by Quadrant (Donut)**: Distribution of revenue across the 4 quadrants.
- **Efficiency Index (Horizontal Bar)**: "Where the Money Is" breakdown.
    - Measures **Efficiency Ratio** = Revenue Share % / Spend Share %
    - *Amplifier*: Ratio > 1.0 (Green)
    - *Balanced*: Ratio 0.75 - 1.0 (Amber)
    - *Drag*: Ratio < 0.75 (Red)
- **Decision Impact Timeline**: Scatter plot of weekly action windows, colored by impact magnitude.

#### 2.2.2 Performance Breakdown Views
- **Match Type Analysis**: Table with Spend, Sales, ROAS, ACoS, CTR, CVR breakdown.
- **Trend Analysis**: Dual-axis time-series chart (Bar vs Line) for custom metric comparison (e.g., Sales vs ACOS).

#### 2.2.3 Period Comparison
- Configurable timeframes: Weekly, Monthly, Quarterly, Yearly (for trends)
- Default view: Last 30 Days (snapshot)

### 2.3 Data Flow

```
Session State / Database
        │
        ▼
┌─────────────────────┐
│  Date Range Filter  │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Metric Calculation │ ← ROAS, ACoS, CVR, CTR
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Period Comparison  │ ← vs. previous period
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Visualization      │ ← Charts, tables, KPIs
└─────────────────────┘
```

---

## 3. Optimizer Model

### 3.1 Overview
The Optimizer Model is the core intelligence of the system. It analyzes performance data and generates three types of optimization recommendations:
1. **Harvest** - Promote high-performing search terms to exact match
2. **Negative** - Block wasteful or bleeding search terms
3. **Bid** - Adjust bids for optimal ROI

### 3.2 Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| TARGET_ROAS | 3.5 | Target Return on Ad Spend |
| TARGET_ACOS | 25% | Target Advertising Cost of Sale |
| MIN_IMPRESSIONS | 200 | Minimum impressions for analysis |
| MIN_CLICKS | 3 | Minimum clicks for analysis |
| MIN_SPEND | 5.0 | Minimum spend (AED) for analysis |

### 3.3 Harvest Module

#### 3.3.1 Purpose
Identify high-performing search terms or ASINs that should be "harvested" as exact match keywords in dedicated campaigns to capture more of their traffic at higher efficiency.

#### 3.3.2 Harvest Criteria

| Criteria | Threshold | Description |
|----------|-----------|-------------|
| Minimum Clicks | 10+ | Statistical significance |
| Minimum Orders | 3+ (CVR-adjusted) | Proven conversion |
| ROAS Requirement | ≥80% of bucket median | Relative performance |

#### 3.3.3 Winner Selection Logic
When the same search term appears in multiple campaigns:
1. Calculate **Winner Score** = Sales + (ROAS × 5)
2. Select campaign with highest score as **Winner**
3. Other campaigns become targets for **Isolation Negatives**

#### 3.3.4 Output
- Harvest candidate list with winner campaign/SKU
- Recommended bid (based on historical CPC × efficiency multiplier)
- Bulk file template for creating exact match keywords

---

### 3.4 Negative Module (Defence)

#### 3.4.1 Purpose
Identify search terms that should be negated to stop wasted spend. Two types:
1. **Isolation Negatives** - Harvest terms to negate in non-winner campaigns
2. **Performance Negatives** (Bleeders) - High-spend, zero-conversion terms

#### 3.4.2 Isolation Negative Logic
```
For each Harvested Term:
    Winner Campaign = Campaign with highest winner score
    
    For each OTHER campaign where term appears:
        Create Negative Keyword for that campaign
        (Prevents cannibalization, funnels traffic to winner)
```

#### 3.4.3 Performance Negative (Bleeder) Criteria

| Type | Criteria | Description |
|------|----------|-------------|
| **Soft Stop** | Clicks ≥ Expected × 2, Orders = 0 | High click, no conversion |
| **Hard Stop** | Clicks ≥ Expected × 3, Orders = 0 | Very high waste |
| **High Spend** | Spend > Threshold, ROAS = 0 | Burning budget |

**Expected Clicks Calculation**:
```
Account CVR = Clamped(Account Orders / Account Clicks, 1%, 10%)
Expected Clicks = 1 / Account CVR
Soft Threshold = Expected Clicks × 2
Hard Threshold = Expected Clicks × 3
```

> **Empirical Validation (Feb 2026, 427 performance negatives):**
> - Confirmed block rate: 92% (including correctly isolated terms)
> - True false positive rate: 2.6%
> - **Conclusion**: 2x/3x multipliers validated, no adjustment required.
> - *Note: 79/90 apparent premature negations were correctly isolated harvest terms — classification requires cross-reference with HARVEST actions before labeling as a false positive.*

#### 3.4.4 ASIN Detection
Identifies Product Targeting (PT) negatives separately:
- Pattern: `B0` followed by 8 alphanumeric characters
- Pattern: `asin="..."` or `asin-expanded="..."`

#### 3.4.5 Output Categories
| Category | Entity Type | Application Level |
|----------|-------------|-------------------|
| Negative Keywords | Keyword | Campaign or Ad Group |
| Negative Product Targeting | ASIN | Campaign or Ad Group |
| Your Products Review | Own ASINs | Manual review (no auto-action) |

---

### 3.5 Bid Optimizer Module

#### 3.5.1 Purpose
Calculate optimal bid adjustments for all targets based on performance vs. target ROAS, using a bucketed approach.

#### 3.5.2 Bucketing Strategy

| Bucket | Criteria | Description |
|--------|----------|-------------|
| **Exact** | Match Type = EXACT only | Manual keyword bids |
| **Product Targeting** | `asin=`, `asin-expanded=` | ASIN/PT bids |
| **Broad/Phrase** | Match Type = BROAD or PHRASE | Keyword bids |
| **Auto/Category** | Match Type = AUTO or targeting is auto-type | Auto campaign targets |

#### 3.5.3 Bid Calculation Formula
```
Performance Gap = (14d_avg_ROAS / Target ROAS) - 1

If Performance Gap > 0 (Outperforming):
    Bid Multiplier = 1 + (Gap × 0.5)  # Scale up cautiously
    New Bid = Current CPC × Bid Multiplier
    Cap at 2× current bid

If Performance Gap < 0 (Underperforming):
    Bid Multiplier = 1 + (Gap × 0.35)  # Scale down conservatively
    New Bid = Current CPC × Bid Multiplier
    Floor at 50% current bid

Clamp New Bid: Min = 0.10 AED, Max = 20.00 AED
```

*Note: "14d_avg_ROAS" refers to the 14-day rolling average ROAS from `target_stats`, calculated as `SUM(sales last 14d) / SUM(spend last 14d)`, not a point-in-time snapshot.*

#### 3.5.4 Decision Cooldown (NEW - V2)
- Before any bid action fires, check `actions_log` for prior `BID_CHANGE` on the same Campaign + Ad Group + Target within 17 days.
- **Maturity formula**: `(action_date + 17 days) <= latest_data_date`
- Immature targets are logged as "Pending Observation" and not actioned.
- **Rationale**: Prevents stacked changes before prior action can be measured, ensures clean pre/post windows for the Impact Model.

#### 3.5.5 Visibility Boost (NEW - Dec 2025)

For targets that are **not winning auctions** despite running for 2+ weeks.

| Condition | Threshold |
|-----------|-----------|
| Data window | ≥ 14 days |
| Impressions | < 100 (not winning auctions) |
| Conversion Gate | orders > 0 OR (clicks >= 5 AND CVR > 0) |

> **Note:** 0 impressions = bid SO low it can't even enter auctions. Paused targets are identified by `state='paused'`, not impressions.

**Eligible Match Types:**
- ✅ Exact, Phrase, Broad (explicit keyword choices)
- ✅ Close-match (most relevant auto type)

**NOT Eligible (Amazon decides relevance):**
- ❌ loose-match, substitutes, complements
- ❌ ASIN targeting (product targeting)
- ❌ Category targeting

**Action:** Increase bid by **30%** to gain visibility. 
If conversion gate is failed (zero-converting target), log as `REVIEW_FLAG` not `BID_CHANGE`. This was a known gap from v1 that was generating waste on non-converting targets.

**Rationale:**
- High impressions + low clicks = CTR problem (not bid issue)
- LOW impressions = bid not competitive (needs boost)
- Only boost keywords the advertiser explicitly chose

#### 3.5.6 Exclusions
- Terms already in Harvest list (will be promoted to exact)
- Terms already in Negative list (will be blocked)
- Low-data targets (below minimum thresholds)

#### 3.5.7 Minimum Click Thresholds by Action Type
- **Promote (bid increase)**: MIN_CLICKS = 15
- **Decrease (bid reduction)**: MIN_CLICKS = 3
- **Rationale**: Asymmetric thresholds reflect that promoting needs statistical confidence, while decreasing does not (you don't need much data to know something isn't converting).

#### 3.5.8 ROAS Target by Bucket
The optimizer applies different multipliers to the global `TARGET_ROAS` based on the semantic match type bucket:
  - **Exact**: 1.00x
  - **Broad/Phrase**: 0.85x
  - **Product Targeting**: 0.80x
  - **Auto/Category**: 0.65x
- **Rationale**: Auto campaigns are discovery by design and structurally produce lower ROAS. Using the exact same target penalizes them incorrectly.

#### 3.5.9 Commerce Intelligence Flags (V2.1)
The optimizer consumes real-time commerce data (SP-API inventory, business reports) via the `commerce_metrics` view to apply situational awareness before committing bid decisions.

**Supported Flags & Behaviors:**
1. **`INVENTORY_RISK`**:
   - *Condition*: ASIN has `< 14 days` of FBA supply (`fulfillable_quantity / avg_daily_units`).
   - *Behavior*: Overrides any calculated bid increase to a "Hold: Suppressed" state to prevent stocking out.
2. **`HALO_ACTIVE`**:
   - *Condition*: Ad Group Total Sales > 2.5x Ad Group Ad Sales (high organic halo effect).
   - *Behavior*: Converts a bid decrease (if warranted by poor ROAS) into a "Hold: Protected" state to avoid collapsing organic rank.
3. **`LAUNCH_PHASE`**:
   - *Condition*: ASIN lifecycle is explicitly marked `LAUNCH` in `advertised_product_cache`.
   - *Behavior*: Protects from strict ROAS-based bid decreases (Hold: Protected) to allow for data gathering and indexing.
4. **`CANNIBALIZE_RISK`**:
   - *Condition*: ASIN is the #1 organic rank for a search term, AND the ad ROAS < 1.0 (Exact match only).
   - *Behavior*: Overrides bid to "Hold" to prevent spending on a term that is already organically dominated.
5. **`BSR_DECLINING`**:
   - *Condition*: ASIN's BSR has worsened by >20% WoW AND ad impressions have dropped.
   - *Behavior*: Overrides specific conservative down-bids to maintain visibility.

#### 3.5.10 Output
- Bid adjustment recommendations per target
- Grouped by bucket (Exact, PT, Broad/Phrase, Auto)
- Before/After bid comparison
- Expected impact calculation
- Commerce Flags triggered (e.g. `INVENTORY_RISK`, `HALO_ACTIVE`)

---

### 3.6 Campaign Launcher Module

#### 3.6.1 Purpose
Generate Amazon bulk upload files for creating new campaigns based on optimization results.

#### 3.6.2 Launch Types

| Type | Use Case | Output |
|------|----------|--------|
| **Harvest Launch** | Create exact match campaigns from harvest candidates | New campaigns + keywords |
| **Cold Start Launch** | Launch new product campaigns from scratch | Full campaign structure |

#### 3.6.3 Harvest Launch Structure
```
For each Harvested Keyword:
    1. Create Campaign: "[PRODUCT]_Harvest_Exact"
    2. Create Ad Group: "[KEYWORD]_AG"
    3. Create Keyword: EXACT match
    4. Set Bid: Momentum Bid = Historical CPC × Efficiency Multiplier
```

#### 3.6.4 Cold Start Launch Structure
- Auto Campaign (discovery)
- Broad Match Campaign
- Exact Match Campaign (if seeds provided)
- Product Targeting Campaign (if competitor ASINs provided)

#### 3.6.5 Output
- Amazon-compatible bulk upload XLSX file
- Includes: Campaign, Ad Group, Keyword/PT rows
- Full bulk sheet schema (67 columns)

---

### 3.7 Bulk Export Module

#### 3.7.1 Purpose
Generate Amazon-compliant bulk upload files for all optimization actions.

#### 3.7.2 Export Types

| Type | Contents | Entity Type |
|------|----------|-------------|
| **Negatives Bulk** | Negative keywords + PT | Negative Keyword, Negative Product Targeting |
| **Bids Bulk** | Bid updates | Keyword, Campaign Negative Keyword, Product Targeting |
| **Harvest Bulk** | New exact match keywords | Keyword |
| **Combined Bulk** | All actions in one file | Mixed |

#### 3.7.3 Validation Rules
- Campaign/Ad Group ID matching (uses Bulk ID Mapping)
- ASIN format validation
- Duplicate detection
- Entity type consistency

#### 3.7.4 Bulk File Schema
Standard Amazon bulk upload columns (67 total):
- Product, Entity, Operation
- Campaign Id, Ad Group Id, Keyword Id, Product Targeting Id
- Campaign Name, Ad Group Name
- Bid, State
- Keyword Text, Negative Keyword Text
- Product Targeting Expression
- Match Type, etc.

---

## 4. Impact Model

### 4.1 Overview
The Impact Model measures the real-world effectiveness of optimization actions by comparing performance before and after implementation.

### 4.2 Measurement Methodology

```
Action Logged (T0)
      │
      ▼
┌─────────────────────┐
│  "Before" Period    │ ← 14 days before T0
│  (Baseline)         │
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  "After" Period     │ ← 14 days after T0
│  (Measurement)      │
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Delta Calculation  │ ← After - Before
└─────────────────────┘
```

### 4.3 Key Metrics

| Metric | Calculation | Description |
|--------|-------------|-------------|
| **Revenue Impact** | (After Sales - Before Sales) | Incremental revenue |
| **ROAS Change** | (After ROAS - Before ROAS) | Efficiency change |
| **Spend Change** | (After Spend - Before Spend) | Budget impact |
| **Implementation Rate** | Executed / Total Actions | Applied vs. logged |

### 4.4 Action Types Tracked

| Action Type | Description | Expected Impact |
|-------------|-------------|-----------------|
| NEGATIVE_ISOLATION | Harvest term negated in source | Reduced waste, focused traffic |
| NEGATIVE_PERFORMANCE | Bleeder term blocked | Direct cost savings |
| BID_INCREASE | Bid increased for performer | More traffic, higher sales |
| BID_DECREASE | Bid decreased for underperformer | Cost savings, improved efficiency |
| **VISIBILITY_BOOST** | Bid +30% for low-impression keywords | More auction wins, increased traffic |
| HARVEST_NEW | New exact match keyword created | Higher conversion on proven terms |

### 4.5 Dashboard Components

- **Hero Tiles**: Actions, ROAS Change, Revenue Impact, Implementation %
- **Waterfall Chart**: Revenue contribution by action type
- **Winners/Losers Chart**: Top/bottom performing actions
- **Drill-Down Table**: Individual action details with before/after

### 4.5 Validation Methodology

#### 4.5.1 Status Definitions (See METHODOLOGY.md for full details)

| Status | Meaning | Criteria |
| :--- | :--- | :--- |
| **✓ Confirmed blocked** | Negative successfully blocked | After Spend = $0.00 |
| **✓ Normalized match** | Negative significantly reduced spend | Drop ≥50% more than account baseline drift |
| **✓ Harvested (complete)** | Source term migrated fully | Source After Spend = $0.00 |
| **✓ Harvested (90%+ blocked)** | Near-complete migration | Source spend dropped ≥90% |
| **✓ CPC Validated** | Bid change verified via CPC | Observed CPC within ±15% of suggested bid |
| **✓ Directional match** | Bid verified via direction | CPC changed >5% in intended direction |
| **✓ Spend Eliminated** | Bid Down killed waste | Action was BID_DOWN, but After Spend went to $0 |
| **⚠️ NOT IMPLEMENTED** | Action failed/ignored | Spend continued or CPC didn't move |

### 4.6 Impact Calculation Methodology

#### 4.6.1 Impact Formulas
Different logic is applied based on the nature of the action:

| Action Type | Formula | Interpretation |
| :--- | :--- | :--- |
| **NEGATIVE** | `+Before Spend` | **Cost Avoidance** (Profit Saved) |
| **HARVEST** | `+10% × Sales Lift` | **Efficiency Gain** (Estimated 10% lift) |
| **BID CHANGE** | `(Actual Sales) - (Expected Sales)` | **Counterfactual** (Action-Driven Lift) |
| **SPEND ELIMINATED** | `(Δ Sales) - (Δ Spend)` | **Profit Change** (Sales Lost - Spend Saved) |

#### 4.6.2 Counterfactual Model (for Bids)
For bid optimizations, we ask: *"What would have happened if we didn't act?"*
1. **Expected Clicks** = `After Spend / Before CPC`
2. **Expected Sales** = `Expected Clicks × Baseline SPC`
3. **Decision Impact** = `Actual After Sales - Expected Sales`

#### 4.6.3 Guardrails & Capping
To prevent impact inflation from low-data targets:
1. **Low Sample (<5 Clicks)**: Impact forces to 0.
2. **ROAS Capping**: For medium-confidence targets (5-20 clicks), baseline SPC is capped using the account's High-Confidence derived ROAS limit (`Median + 1*StdDev`).
3. **Confidence Weighting**: Linear dampening (0.33 to 1.0) applied to targets with 5-15 clicks.
4. **Ad Group Fallback Penalty**: A **50% penalty** is applied to confidence weight if impact calculation relies on Ad Group level fallback data.

#### 4.6.4 Market Drag Exclusion
Actions classified as "Market Drag" (Market Down + Decision Down) are **excluded** from the attributed Net Impact to prevent penalizing the optimizer for broad market downturns.

| Metric | Formula | Applies To |
|--------|---------|------------|
| **Decision Impact** | Actual Sales - Expected Sales | Bid changes, Harvests |
| **Spend Avoided** | Before Spend - After Spend (if positive) | Negatives only |

#### 4.7.5 Interpretation

| Decision Impact | Meaning |
|-----------------|---------|
| **Positive** | Bid decision generated MORE sales than counterfactual |
| **Zero** | Performance matched expectations |
| **Negative** | Bid decision generated LESS sales than counterfactual |

### 4.8 Multi-Horizon Impact Measurement

#### 4.8.1 Purpose
Amazon's attribution window is 7-14 days. Measuring at 7 days produces incomplete data and false negatives. We use a principled multi-horizon approach for accurate impact measurement.

#### 4.8.2 Measurement Horizons

| Horizon | Before Window | After Window | Maturity | Purpose |
|---------|---------------|--------------|----------|---------|
| **14D** | 14 days | 14 days | 17 days | Early signal — did the action have an effect? |
| **30D** | 14 days | 30 days | 33 days | Confirmed — is the impact sustained? |
| **60D** | 14 days | 60 days | 63 days | Long-term — did the gains hold? |

#### 4.8.3 Maturity Formula
```
is_mature(horizon) = (action_date + horizon_days + 3) ≤ latest_data_date
```

- **Before window**: Always 14 days (fixed baseline)
- **After window**: 14, 30, or 60 days (per selected horizon)
- **Buffer**: 3 days for attribution to settle

#### 4.8.4 Example (data through Dec 28)
| Action Date | 14D Mature? | 30D Mature? | 60D Mature? |
|-------------|-------------|-------------|-------------|
| Dec 11 | ✅ (Dec 28) | ❌ (Jan 13) | ❌ (Feb 12) |
| Nov 25 | ✅ | ✅ (Dec 28) | ❌ (Jan 27) |
| Oct 1 | ✅ | ✅ | ✅ |

#### 4.8.5 Dashboard Behavior
- User selects horizon via radio toggle (14D / 30D / 60D)
- **Aggregates** (ROAS change, revenue impact, win rate) include ONLY actions mature for selected horizon
- **Pending actions** excluded from aggregates, shown separately with expected maturity date
- Action counts will decrease at longer horizons (fewer actions are old enough)

> **Why not 7 days?**  
> Most PPC tools measure at 7 days. This captures only ~75% of attributed conversions and measures bid changes before they stabilize. We choose accuracy over speed.

### 4.9 Decision Outcome Matrix (Jan 2026 - Counterfactual Framework)

#### 4.9.1 Philosophy
Isolate **decision quality** from **market conditions** by comparing actual performance to a counterfactual baseline.

#### 4.9.2 Counterfactual Logic

**X-Axis: Expected Trend %**
- Formula: `(Expected Sales - Before Sales) / Before Sales * 100`
- Expected Sales = `(New Spend / Baseline CPC) × Baseline SPC`
- **Translation**: "If we maintained our old efficiency, what would sales be at the new spend level?"

**Y-Axis: vs Expectation %**
- Formula: `Actual Change % - Expected Trend %`
- **Translation**: "How much did we BEAT or MISS the counterfactual baseline?"

#### 4.9.3 Quadrants

| Quadrant | Criteria | Meaning | Attribution |
|----------|----------|---------|-------------|
| **Offensive Win** | X≥0, Y≥0 | Spend increased + beat baseline → Efficient scaling | ✅ Included |
| **Defensive Win** | X<0, Y≥0 | Market shrank, but we beat the expected drop → Good defense | ✅ Included |
| **Decision Gap** | X≥0, Y<0 | Spend increased but missed expectations → Inefficient scale | ✅ Included |
| **Market Drag** | X<0, Y<0 | Market shrank AND we underperformed → External confound | ❌ **EXCLUDED** |

#### 4.9.4 Decision-Attributed Impact (Refined Hero Metric)

**Formula**: `Sum(Offensive Wins + Defensive Wins + Decision Gaps)`

**Critical Exclusion**: Market Drag is **EXCLUDED** from all impact totals.

**Reasoning**:
- Market Drag represents external headwinds we didn't control
- Including it would conflate market luck with decision quality
- We ONLY attribute impact where our DECISION had clear directional influence

**Display Format**:
- Main Number: Net Impact (Green if positive, Red if negative)
- Breakdown: "✅ Wins: +X (Offensive + Defensive) | ❌ Gaps: -Y"
- Footnote: "ℹ️ Z actions excluded (Market Drag — ambiguous attribution)"

### 4.10 Capital Protected (Refined Logic)

**Definition**: Wasteful spend eliminated from confirmed negative keyword blocks.

**Formula**: `Sum of before_spend for NEGATIVE actions where observed_after_spend == 0`

**Why This Works**:
- Only counts actions **INTENDED** to protect capital (negatives)
- `after_spend == 0` proves the block was successful
- Bid increases **SHOULD** increase spend — that's scaling winners

**Display**: "From X confirmed negatives" + "Confidence: High"

**Why Not Total Spend Reduction?**
- Only NEGATIVE actions have the explicit goal of capital protection
- Counting only confirmed blocks (spend = 0) provides clear proof

### 4.12 Outcome Logging (Learning Loop - V2)
- Provided by the `record_action_outcomes()` function.
- Adds columns to `actions_log`: `outcome_roas_delta`, `outcome_label`, `outcome_evaluated_at`.
- **Evaluation window**: Scans actions between 17-47 days old with a null outcome.
- **Label thresholds**: `improved` (> +0.1), `worsened` (< -0.1), `neutral` otherwise.
- **Purpose**: Generates labeled training data for future ML models.
- **⚠️ CRITICAL ML CAVEAT (Market Baseline Drift)**: 
  Raw outcome labels reflect absolute ROAS delta. Before ML 
  training, labels must be market-adjusted by comparing target ROAS 
  delta against account baseline drift for the same period. Raw 
  worsened rate of ~43% is consistent across all action types 
  including holds, confirming market-driven baseline rather than 
  decision-caused harm.

### 4.11 ROAS Attribution Decomposition (V2 - Jan 2026)

#### 4.11.1 Purpose
Explain the movement from **Baseline ROAS** to **Actual ROAS** by isolating external market forces from internal structural effects and decision impact.

#### 4.11.2 Baseline Definition (Rolling Window)
- **Methodology**: Rolling Period-over-Period (PoP)
- **Current Period**: [Latest Date - X Days] to [Latest Date]
- **Baseline Period**: [Current Start - X Days] to [Current Start]
- **Rationale**: Accounts for seasonality and recent trend shifts better than fixed historical baselines.

#### 4.11.3 Waterfall Formula
$$ \text{Actual} = \text{Baseline} + \text{Market} + \text{Structure} + \text{Decisions} + \text{Residual} $$

| Component | Definition | Formula |
|-----------|------------|---------|
| **Market Forces** | External tailwinds/headwinds | $\Delta \text{CPC Impact} + \Delta \text{CVR Impact} + \Delta \text{AOV Impact}$ |
| **Structural Effects** | Drag from scaling or new launches | $\text{Scale Effect} + \text{Portfolio Effect}$ |
| **Decision Impact** | Value from optimizations | $\text{Verified Impact Value} / \text{Current Spend}$ |
| **Residual** | Unexplained efficiency change | $\text{Actual} - (\text{Baseline} + \text{Market} + \text{Structure} + \text{Decisions})$ |

#### 4.11.4 Interpretation Guide
- **Positive Residual**: "Performance Beat" — you maintained efficiency despite scaling (beat the scale penalty) or benefitted from organic halo.
- **Negative Residual**: Efficiency dropped more than expected (check for unmeasured external factors).


## 5. Forecast Model (Simulator)

### 5.1 Overview
The Forecast Model simulates the expected impact of proposed optimizations before implementation, helping advertisers understand potential outcomes.

### 5.2 Simulation Approach

#### 5.2.1 Elasticity Model
```
For each Bid Change:
    Δ CPC = Bid Change × CPC Elasticity
    Δ Clicks = Δ CPC × Click Elasticity
    Δ CVR = Δ Click Volume × CVR Elasticity
    
    Projected Sales = Current Sales × (1 + Δ Clicks) × (1 + Δ CVR)
    Projected Spend = Current Spend × (1 + Δ CPC) × (1 + Δ Clicks)
```

#### 5.2.2 Elasticity Scenarios

| Scenario | CPC Elasticity | Click Elasticity | CVR Effect | Probability |
|----------|---------------|------------------|------------|-------------|
| Conservative | 0.30 | 0.50 | 0% | 15% |
| Expected | 0.50 | 0.85 | +10% | 70% |
| Aggressive | 0.60 | 0.95 | +15% | 15% |

#### 5.2.3 Harvest Efficiency Multiplier
For new exact match keywords (harvest):
```
Harvest Efficiency = 1.30  # 30% efficiency gain from exact match
Projected Revenue = Historical Revenue × Harvest Efficiency
```

#### 5.2.4 Harvest Launch Multiplier
New harvest keywords start with an aggressive bid to win impressions:
```
Harvest Launch Multiplier = 2.0  # 2x the source keyword's CPC
New Bid = Source_CPC × Launch_Multiplier
```
**Rationale**: Exact match auctions are more competitive. Starting at 2x the source CPC ensures the new keyword can win impressions. The bid optimizer will correct down if performance is poor.

### 5.3 Simulation Output

| Metric | Description |
|--------|-------------|
| **Projected Spend** | Expected spend after bid changes |
| **Projected Sales** | Expected sales after optimizations |
| **Projected ROAS** | Expected ROAS improvement |
| **Confidence Range** | Low / Expected / High scenarios |

### 5.4 Visualization

- **Before/After Comparison**: Key metrics side-by-side
- **Confidence Intervals**: Probabilistic range of outcomes
- **Scenario Analysis**: Conservative to Aggressive projections

---

## 6. Data Persistence

### 6.1 Database Architecture

The system uses PostgreSQL for persistent storage:

| Table | Purpose |
|-------|---------|
| `accounts` | Account registry |
| `target_stats` | Aggregated performance data |
| `actions_log` | Optimization action history |
| `bulk_mappings` | Campaign/AdGroup/Keyword IDs |
| `category_mappings` | SKU to Category mapping |
| `advertised_product_cache` | Campaign to SKU/ASIN mapping |
| `account_health_metrics` | Periodic health snapshots |

### 6.2 Session State vs. Database

| Data | Session State | Database |
|------|--------------|----------|
| Fresh upload (raw) | ✅ Full granularity | Aggregated weekly |
| Historical data | ❌ Lost on reload | ✅ Persistent |
| Optimization results | ✅ Current session | ❌ Not persisted |
| Action history | ❌ | ✅ Persistent |

---

## 7. User Interface

### 7.1 Navigation Structure

```
Home (Account Overview)
├── Data Hub (Upload & Manage)
├── Performance Snapshot (Reports)
├── Optimizer Pipeline V2.1 (Beta)
│   ├── Pre-Run Intelligence Brief (Account Health)
│   ├── Decisions View
│   │   ├── Bids
│   │   ├── Defence (Negatives)
│   │   └── Harvest
│   └── Intelligence View
│       ├── Wasted Spend Matrix
│       └── Commerce Flags Overrides
├── Legacy Modals (Deprecated)
│   ├── Actions Review
│   └── Simulator
├── ASIN Mapper
└── AI Strategist
```

### 7.2 Key UI Patterns

- **Premium Dark Theme**: Modern glassmorphism design
- **Lazy Loading**: Heavy modules load on-demand
- **Fragmented UI**: Interactive elements don't cause full reruns
- **Responsive Layout**: Adapts to screen size

### 7.3 Optimizer V2.1 UX (Beta)

The V2.1 Optimizer introduces a modernized, commerce-aware workflow split into distinct views:
- **Pre-Run Intelligence Brief**: Before optimization, the user sees Account Health, spend trends, and a summary of pending decisions from the last run to provide context.
- **View 1 (Decisions)**: Replaces the fragmented tabs with a single scrollable page consolidating Bid Changes, Negatives, and Harvest. Each section shows top rows inline with a "Decision Memo" reason column explaining the AI's rationale in plain English.
- **View 2 (Intelligence)**: Focuses on root-cause analysis, featuring the Wasted Spend Heatmap and the Commerce Flags panel to visualize which bids were suppressed or boosted due to inventory risks or organic halo effects.

---

---

## 8. Performance & Infrastructure

### 8.1 Database Reliability
*   **Connection Pooling**: Uses `psycopg2` thread-safe connection pool via `core.db_manager`.
*   **Robustness**: Handled via `@contextmanager` to ensure connections are always returned to the pool, preventing exhaustion timeouts (max_connections).
*   **Latency**: Invite validation and heavy dashboard loads are optimized with index usage and pooled connections.

---

## 9. Multi-Tenancy & Access Control

### 9.1 Organization Model
*   **Hierarchy**: User -> Organization -> Accounts.
*   **Invitation Flow**: 
    1.  Admin generates secure token link.
    2.  User accepts link -> Account created in Organization.
    3.  User assigned Role (`VIEWER`, `OPERATOR`, `ADMIN`).

### 9.2 Zero-State Experience
*   **Onboarding Wizard**: 3-step guide for new users (Welcome -> Value Prop -> Connect).
    *   **Amazon LWA OAuth Integration**: Step 3 includes a direct "Connect Amazon Ads Account" button. It generates a unique `client_id` (state parameter) and securely connects via Amazon's OAuth endpoint. Supabase Edge Functions manage the callback and token storage, redirecting seamlessly back to the Streamlit app state.
*   **Empty States**:
    *   **No Accounts**: "Connect your first account" CTA.
    *   **No Data**: "Syncing in progress" state.
    *   **Filtered Empty**: Friendly "No results" message.

## 9. Organization & User Governance (Phases 1-4)

### 9.1 System Model (Canonical)
The system follows a strict hierarchy where **Organizations** are the primary entities, owning both **Users** (Seats) and **Amazon Accounts**.

```
Organization (Billing Entity)
├── Users (Seats)
│   └── Role (Global + Account Overrides)
└── Amazon Accounts (Resource)
```

### 9.2 Organization Model
- **Attributes**: Name, Type (Agency/Seller), Subscription Plan, Amazon Account Limit.
- **Rules**:
    - Organizations own Amazon accounts (not users).
    - Amazon accounts are **hard-capped** by plan.
    - Users (Seats) are **unlimited** but billable (Soft enforcement).

### 9.3 User & Role Model

#### 9.3.1 Global Roles (Hierarchy)
Roles are cumulative. Higher roles inherit all permissions of lower roles.

| Role | Access Level | Description | Key Capabilities |
|------|--------------|-------------|------------------|
| **OWNER** | Level 4 | Strategic Control | Billing, Delete Org, Transfer Ownership. |
| **ADMIN** | Level 3 | Operational Control | Manage Users, Add Amazon Accounts, System Config. |
| **OPERATOR** | Level 2 | Execution | Run Optimizers, Upload Data, Trigger Actions. |
| **VIEWER** | Level 1 | Read-Only | View Dashboards, Download Reports. |

#### 9.3.2 Login & Authentication
- **Organization-Scoped**: Users belong to exactly one Organization.
- **Authentication**: Email + Password.
- **Session**: Stateful session tracking current User, Role, and Active Account permissions.

### 9.4 Access Control Logic

#### 9.4.1 Global vs. Account-Specific Access
By default, a user's **Global Role** applies to ALL Amazon accounts in the organization.

#### 9.4.2 Account Access Overrides (Phase 3.5)
To support Agency use cases (e.g., restricting interns from VIP clients), Admins can set **Account-Specific Overrides**.
- **Downgrade Only**: Overrides can only *reduce* permissions (e.g., OPERATOR → VIEWER). They cannot grant more access than the Global Role.
- **Resolution**: `Effective_Permission = MIN(Global_Role, Override_Role)`

| Global Role | Account Override | Effective Access | Scenario |
|-------------|------------------|------------------|----------|
| OPERATOR | NONE (Default) | OPERATOR | Standard workflow |
| OPERATOR | VIEWER | VIEWER | Intern on VIP client |
| OPERATOR | NO_ACCESS | BLOCKED | Partitioned teams |

### 9.5 Workflows

#### 9.5.1 User Invitation
1.  Admin enters email & selects Global Role.
2.  System sends invite link.
3.  User sets password & joins.
4.  Billing updates automatically (new billable seat).

#### 9.5.2 Permission Management
- Admins can modify Global Roles or set Account Overrides at any time via the "Team Settings" UI.
- Changes take effect immediately (requiring session refresh for active users).

---

## 10. Open Issues & Backlog

### 8.1 Known Issues

| Issue | Priority | Description |
|-------|----------|-------------|
| Negative detection discrepancy | High | DB data shows fewer negatives than session state |
| Weekly aggregation granularity | Medium | Daily patterns may be lost during weekly aggregation |

### 8.2 Future Enhancements

- [ ] Real-time Amazon Ads API integration
- [ ] Automated scheduled optimization runs
- [ ] Inventory awareness before bid increases (requires SP-API)
- [ ] Multi-marketplace support
- [ ] Budget allocation optimizer
- [ ] Seasonality-aware ROAS targets (requires 12+ months data)
- [ ] Dayparting bid adjustments (data exists, not yet implemented)
- [ ] Cannibalisation detection across duplicate targets
- [ ] New product launch phase detection

### 8.3 Completed (V2)
- [x] Cooldown logic implementation (prevents stacked changes)
- [x] Visibility boost conversion gate (prevents boosting non-converting terms)

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **ROAS** | Return on Ad Spend = Sales / Spend |
| **ACoS** | Advertising Cost of Sale = Spend / Sales × 100 |
| **CVR** | Conversion Rate = Orders / Clicks |
| **CTR** | Click-Through Rate = Clicks / Impressions |
| **CPC** | Cost Per Click = Spend / Clicks |
| **Harvest** | Promoting a proven search term to exact match |
| **Isolation** | Negating a harvested term in non-winner campaigns |
| **Bleeder** | High-spend search term with no conversions |
| **PT** | Product Targeting (ASIN-based targeting) |
| **Normalized Validation** | Comparing target's change against account baseline to distinguish action-driven impact from market shifts |
| **Directional Match** | CPC moved in expected direction (bid up → CPC up) by >5% |
| **Baseline Beat** | Target's ROAS/spend change outperformed account average |
| **Confirmed Action** | Action validated via CPC match, directional check, or normalized threshold |
| **Decision Impact** | Market-adjusted revenue change attributable to advertiser decisions |
| **30D Rolling SPC** | 30-day average Sales Per Click, used as stable baseline for counterfactual calculation |
| **Harvest Launch Multiplier** | 2.0x bid multiplier for new harvest keywords to compete in exact match auctions |
| **Confidence Weight** | Dampening factor (0-1) based on before_clicks / 15, reduces noise from low-data decisions |
| **Final Decision Impact** | Weighted impact = decision_impact × confidence_weight |
| **Impact Tier** | Classification: Excluded (<5 clicks), Directional (5-14), Validated (15+) |
| **actual_after_days** | Calendar days from action_date to latest data (not report file count) |
| **Z-Score Confidence** | Statistical confidence based on standard error of mean impact |

---

## Appendix B: File Locations

| Component | File Path |
|-----------|-----------|
| Data Hub | `core/data_hub.py` |
| Optimizer | `features/optimizer.py` |
| Performance Snapshot | `features/performance_snapshot.py` |
| Impact Dashboard | `features/impact_dashboard.py` |
| Simulator | `features/simulator.py` |
| Campaign Creator | `features/creator.py` |
| Bulk Export | `features/bulk_export.py` |
| Database Manager | `core/postgres_manager.py` |
| Main UI | `ppcsuite_v4_ui_experiment.py` |
