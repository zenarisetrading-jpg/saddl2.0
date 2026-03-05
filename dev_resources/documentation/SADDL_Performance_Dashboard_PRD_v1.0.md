# SADDL Performance Dashboard
## Product Requirements Document v1.0

**Status:** Ready for Build  
**Author:** SADDL Product  
**Date:** February 23, 2026  
**Scope:** Performance Dashboard (5 tabs) with guardrails, fail-safe behavior, and test coverage

---

## 1. Executive Summary

### 1.1 Purpose

Deliver a single Performance Dashboard experience that serves:
- Executives: fast business health and risk visibility
- PPC managers: campaign and keyword-level actionability
- Inventory operators: stock risk and spend-protection visibility
- Analysts/agencies: transparent intelligence attribution and audit trail

### 1.2 Core Outcome

The dashboard must answer, in one workflow:
- How is the business performing now?
- Where is spend efficient vs wasteful?
- Where is stock risk constraining growth?
- What decisions did SADDL intelligence change or block, and why?

### 1.3 Non-Goals

- No advanced inventory demand forecasting in this phase
- No impression-share-driven bid recommendations until Ads API support is live
- No full optimizer replacement; dashboard is visibility + decision explainability layer

---

## 2. Navigation and Information Architecture

### 2.1 Primary Navigation

- `Performance Dashboard` (top-level tab)

### 2.2 Sub-tabs (in order)

1. `Business Overview`
2. `PPC Overview`
3. `Inventory Overview`
4. `Intelligence`
5. `Product`

### 2.3 Global Controls

- Date range selector (default: last 30 days)
- Comparison mode: vs prior equal-length period
- Time-horizon toggle for trend cards/charts: `14D` / `30D` / `60D` where applicable
- Portfolio/account selector (if multi-account context is enabled)

---

## 3. Metric Definitions and Scoring

### 3.1 Account Health Score (0-100)

Weighted composite score:
- TACOS vs target: `30%`
- Organic vs paid revenue ratio: `25%`
- Inventory health (days of cover): `25%`
- CVR trend direction over 14 days: `20%`

Target fallback defaults (build-time safe defaults):
- ROAS target source: `client_settings.target_roas`; fallback to `3.0x` if null
- TACOS target source: account target config; fallback to `10%` if null/missing

#### 3.1.1 Rendering

- Gauge/dial in top-left of Business Overview
- Three driver callouts below gauge, each with impact point contribution
- Example: `TACOS 4.2% above target - dragging score by 8 points`

#### 3.1.2 Scoring Guardrails

- Clamp final score to `[0, 100]`
- If a component input is missing, reweight remaining components proportionally and show inline `Data partial` badge
- Minimum data floor: at least `2 of 4` components must have valid data to compute a score
- If fewer than 2 components are available, show neutral fallback state (no computed score) with explanation
- Never show empty gauge; fallback to neutral score state with explanation when all components unavailable

### 3.2 KPI Card Behavior (Global)

Each KPI card must show:
- Current value
- Delta vs prior period
- Directional arrow
- Color state:
  - Green: improving
  - Red: declining
  - Grey: flat/insufficient change

Flat threshold defaults:
- Percentage metrics: absolute delta < 0.25 pp
- Currency/count metrics: absolute delta < 1%

---

## 4. Detailed Tab Requirements

## 4.1 Tab 1 - Business Overview

### 4.1.1 Section 1 - Account Health Score

- Composite score gauge using weights in Section 3.1
- 3 ranked score-driver callouts

Acceptance Criteria:
- Gauge loads in <1.5s after filters apply
- Driver callouts reconcile to score decomposition
- Missing-component behavior follows Section 3.1.2
- If fewer than 2 components have data, gauge renders neutral fallback and suppresses misleading numeric score

### 4.1.2 Section 2 - Business Metrics Strip

Cards:
- Total Sales (organic + paid)
- Organic Sales + organic % of total
- Ad Sales
- TACOS
- CVR (blended sessions to orders)
- AOV
- Sessions / Page Views
- Units Sold

Acceptance Criteria:
- Each card includes current, delta, arrow, color state
- All deltas compare against prior equal-length period
- Tooltips provide formula definitions

### 4.1.3 Section 3 - Trend Charts (`14D` / `30D` / `60D`)

Chart A: Paid vs Organic Sales Trend (2 lines)  
Chart B: TACOS Trend + target line overlay  
Chart C: Paid/Organic Sessions (stacked bars)

Acceptance Criteria:
- Toggle updates all three charts in one interaction
- Target TACOS line uses account-level configured target
- If account TACOS target is missing, target line uses default `10%`
- Source split legends are always visible

### 4.1.4 Section 4 - Detailed Performance Table

Columns:
- Parent ASIN/SKU
- Sessions
- Page Views
- CVR
- Units
- Sales
- Ad Spend
- TACOS
- Organic %
- Days of Cover

Behavior:
- Sortable all columns
- Default sort: `TACOS desc`
- Filter by category/product group

Acceptance Criteria:
- Sort and filter interactions persist through pagination
- Exports (if enabled) reflect current sort/filter state

---

## 4.2 Tab 2 - PPC Overview

### 4.2.1 Section 1 - PPC Health Strip

Metrics:
- Total Ad Spend (period)
- Blended ROAS
- ACOS
- Impressions
- CTR
- CPC trend
- Total keywords active

### 4.2.2 Section 2 - Campaign Performance Table

Grouping:
- Exact
- Broad
- Auto

Columns:
- Campaign
- Spend
- Sales
- ROAS
- ACOS
- Impressions
- CTR
- CPC
- Status

ROAS color bands:
- Green: above target
- Amber: within 20% of target
- Red: below target

Target source fallback:
- ROAS target uses `client_settings.target_roas`; if null, use system default `3.0x`

### 4.2.3 Section 3 - Keyword Diagnostics

Top 20 spend keywords with flags:
- Over-spending: ROAS below target
- Under-bidding: high ROAS + low impression share (placeholder until Ads API)
- Zero-conversion keywords above spend threshold

### 4.2.4 Section 4 - Optimization History

Show last 5 optimizer runs:
- Run date
- Actions applied
- ROAS before vs after (only when measurement window complete)
- Link to Impact Analysis

Acceptance Criteria:
- Incomplete measurement windows are clearly labeled `Pending window`
- Links deep-link to the corresponding run in Impact Analysis

---

## 4.3 Tab 3 - Inventory Overview

### 4.3.1 Section 1 - Portfolio Inventory Health

Metrics:
- Total active SKUs
- SKUs in stock (green)
- SKUs low stock/warning (<14 days cover, amber)
- SKUs OOS (red)
- SKUs suppressed by `INVENTORY_RISK` this run

### 4.3.2 Section 2 - Days of Cover by SKU

- Horizontal bar chart
- One bar per SKU
- Sorted ascending (most at-risk first)
- Color-coded by health state

### 4.3.3 Section 3 - Inventory Table

Columns:
- SKU
- ASIN
- FBA Units
- Days of Cover
- Restock Threshold
- Arrival Rate
- Status
- Ad Spend Blocked (AED value)

### 4.3.4 Section 4 - Restock Alerts

- Ordered urgency list of SKUs below restock threshold

Acceptance Criteria:
- `Ad Spend Blocked` is visible at row and aggregate levels
- Alerts are sorted by lowest days of cover first

---

## 4.4 Tab 4 - Intelligence

### 4.4.1 Section 1 - Intelligence Layer Summary (Last Run)

Run-level panel:
- `INVENTORY_RISK` - bid increases blocked (stock protection)
- `HALO_ACTIVE` - bid caps applied (organic dominance)
- `ORGANIC_CVR` - bids held (organic converting efficiently)
- `BSR_DECLINING` - not live
- `IMPRESSION_SHARE` - pending Ads API

### 4.4.2 Section 2 - Decision Attribution Funnel

Funnel:
- Raw Recommendations
- Intelligence Modified
- Final Actions Applied

### 4.4.3 Section 3 - Intelligence Impact Over Time

Per optimizer run line chart:
- Count of `INVENTORY_RISK` blocks
- Count of `HALO_ACTIVE` adjustments

### 4.4.4 Section 4 - Decision Log

Searchable and filterable log:
- Filter by flag type, date, campaign, keyword
- Full audit trail visibility

Acceptance Criteria:
- Funnel totals reconcile with raw actions_log counts for selected period
- Decision log query latency p95 <= 2.5s at target scale

---

## 4.5 Tab 5 - Product

### 4.5.1 Section 1 - Portfolio Selector

- Dropdown/search by Parent ASIN or product group
- Default: `All Products`

### 4.5.2 Section 2 - Product Metrics at a Glance

For selected product:
- Sales
- Units
- CVR
- Sessions
- Page Views
- TACOS
- Organic %
- FBA Stock
- Days of Cover
- Ad Spend
- ROAS

### 4.5.3 Section 3 - Child ASIN / Variation Breakdown

Variation table per child ASIN/SKU using same metric set

### 4.5.4 Section 4 - Product Trend Charts

- Sales trend
- TACOS trend
- CVR trend
- Toggle: `14D` / `30D` / `60D`

### 4.5.5 Section 5 - Product Intelligence Flags

- Flags fired on selected product in last run
- Decision changes attributable to each flag

Acceptance Criteria:
- Switching parent ASIN updates all product sections atomically
- Child table totals reconcile to parent summary (within rounding tolerance)

---

## 5. Data Sources and Dependency Rules

### 5.1 Primary Data Sources by Tab

- Business Overview: `SP-API Orders`, `Sessions/Page Views`, `commerce_metrics`, `fba_inventory`
- PPC Overview: `STR data`, `actions_log`, `commerce_metrics`
- Inventory Overview: `fba_inventory`, `actions_log` (`INVENTORY_RISK` blocks)
- Intelligence: `actions_log`, optimizer intelligence flags
- Product: joined ASIN-level blend of all above

### 5.2 SP-API Dependency Handling (Fail-Safe Requirement)

If SP-API data is missing for an account:
- Show subtle in-section notice: `SP-API not connected`
- Hide/disable only SP-API-dependent widgets in that section
- Keep PPC Overview and STR-backed views rendering normally
- Never show full-page error for partial data absence

Acceptance Criteria:
- Partial-data tabs remain functional without JS/runtime exceptions
- Notices are localized to affected sections only

---

## 6. Guardrails

### 6.1 Data Guardrails

- Enforce consistent timezone and date-window alignment across all tabs
- Reject divide-by-zero outputs; render `N/A` with tooltip reason
- Null-safe metric aggregation for incomplete daily loads
- Deduplicate actions by `(run_id, entity_id, action_type)` before attribution
- Validate currency normalization (AED display where specified)

### 6.2 Product Guardrails

- No misleading color states when statistical movement is insignificant
- No stale run-level intelligence data without `as_of` timestamp
- Prevent cross-tab metric drift by centralizing shared metric computation
- Persist selected date range/tab filters across sub-tab navigation

### 6.3 Performance Guardrails

- Initial tab paint target: p95 <= 2.5s
- Filter/toggle interaction target: p95 <= 1.0s
- Server-side pagination for tables >500 rows
- Query timeout fallback with recoverable inline notice

### 6.4 Reliability Guardrails

- Graceful degradation for each section on source-table unavailability
- Retry policy for transient data fetch failures (max 2 retries)
- Structured error telemetry for failed widget loads

### 6.5 Security and Compliance Guardrails

- Role-based visibility for account/portfolio data
- No sensitive credential leakage in logs or client payloads
- Audit log access controls for agency/client boundary accounts

### 6.6 UX and Accessibility Guardrails

- Keyboard navigable tables/charts where framework allows
- Color is not sole signal; include icons/labels for status states
- Minimum contrast and readable text at dashboard default zoom

---

## 7. Test Strategy and Coverage

## 7.1 Test Layers

1. Unit tests: metric formulas, score weighting, color-state logic, thresholds
2. Data contract tests: schema/field availability, nullability, type checks
3. Integration tests: source-join correctness across tabs
4. UI tests: render states, localized SP-API notices, sorting/filtering
5. End-to-end tests: core user workflows by persona
6. Regression tests: baseline snapshots for KPI and chart integrity

## 7.2 Required Test Cases (Minimum)

### A. Business Overview

- Score computes correctly under full data and missing-component conditions
- Driver callouts match component contribution math
- TACOS target line renders and updates by account target config
- Table default sort is `TACOS desc`

### B. PPC Overview

- ROAS band coloring matches thresholds exactly
- Keyword Diagnostics selects top 20 by spend for selected window
- Optimization history excludes before/after deltas when window incomplete

### C. Inventory Overview

- Days-of-cover classification: green/amber/red thresholds
- Restock alerts sorted by urgency
- `Ad Spend Blocked` aggregation matches flagged action totals

### D. Intelligence

- Funnel stages reconcile with deduplicated actions_log
- Trend chart counts per run match raw event counts
- Decision log filters compose correctly (flag + date + campaign + keyword)

### E. Product

- Parent selection updates all dependent widgets in single rerun/render cycle
- Child ASIN totals reconcile to parent summary metrics
- Product-level intelligence flags only show relevant ASIN-linked events

### F. Dependency and Failure Handling

- SP-API disconnected: only impacted sections show `SP-API not connected`
- STR-only accounts still render PPC Overview with no hard failure
- Source table timeout returns inline recoverable state, not crash

### G. Performance and Scale

- 5k-row product table with pagination meets latency targets
- Decision log search remains within p95 <= 2.5s under expected load

### H. Security and Access

- Unauthorized account selector access is blocked
- Cross-tenant data leakage tests for decision log and product views

## 7.3 Exit Criteria (Release Gate)

- 100% pass on critical-path tests (A-F)
- >=95% pass on non-critical-path tests (G-H) with documented mitigations
- No P0/P1 defects open
- Observability dashboards available for:
  - widget errors
  - query latency
  - SP-API missing-data rates

---

## 8. Build Sequence and Milestones

Build order:
1. Business Overview
2. Product
3. Inventory Overview
4. Intelligence
5. PPC Overview

Milestone Definition of Done:
- Section-level acceptance criteria met
- Guardrail checks implemented
- Required tests in Section 7 passing
- UX copy for partial-data and failure states reviewed

---

## 9. Open Dependencies

- Ads API integration for impression share-dependent diagnostics (`IMPRESSION_SHARE`, under-bidding confidence upgrade)
- Live `BSR_DECLINING` signal availability
- Finalized long-term target governance for TACOS/ROAS by account (temporary system defaults active: ROAS `3.0x`, TACOS `10%` when config is missing)
