# Impact Analysis v3.0 - Technical Specification

**Version:** 3.0  
**Last Updated:** February 5, 2026  
**Status:** 🔬 Diagnostic Mode (Production deployment pending)

---

## Executive Summary

Impact v3.0 introduces **Confidence Tiering** and **Data Quality Scoring** to ensure accurate impact attribution while maximizing analyzable data volume. This release addresses the "Triple Truth Problem" identified in the February 2026 audit by establishing Postgres as the single source of truth.

### Key Changes from v2.0

| Area | v2.0 | v3.0 |
|------|------|------|
| **Source of Truth** | UI recalculated, DB provided | DB is sole source |
| **Data Quality** | Binary (exclude <5 clicks) | Three-tier confidence system |
| **Baseline Matching** | Target-only | Target → CST → Ad Group fallback chain |
| **Harvest Formula** | +10% × Sales Lift (PRD) | 0.85× Counterfactual (implemented) |
| **Market Drag** | Included in totals | Excluded from headline impact |

---

## 1. Architecture: Single Source of Truth

### 1.1 The Triple Truth Problem (Resolved)

The February 2026 audit identified three competing sources for impact calculations:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   UI Layer      │     │   PostgreSQL    │     │   SQLite        │
│  (transforms.py)│     │ (postgres_mgr)  │     │  (db_manager)   │
│                 │     │                 │     │                 │
│  Recalculates:  │     │  Computes:      │     │  Parallel impl: │
│  - expected_sales│    │  - final_impact │     │  (deprecated)   │
│  - decision_impact│   │  - guardrails   │     │                 │
│  - 0.85x harvest │    │  - validation   │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         ↓                       ↓                      ↓
         └───────────────────────┴──────────────────────┘
                              ⚠️ CONFLICT!
```

### 1.2 v3.0 Resolution

**PostgreSQL is the single source of truth.** The UI layer (`features/impact/`) consumes DB fields without recalculation.

```
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL (Source)                        │
│  - final_decision_impact   (pre-computed, guardrailed)         │
│  - confidence_tier         (gold/silver/bronze)                │
│  - confidence_weight       (0.0 - 1.0)                         │
│  - match_level             (target/cst/ad_group)               │
│  - validation_status       (validated/not implemented)         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      UI Layer (Consumer)                        │
│  - Reads pre-computed fields                                   │
│  - Applies display filters (validated only toggle)             │
│  - NO recalculation of impact values                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Confidence Tiering System

### 2.1 Overview

Instead of binary include/exclude, v3.0 uses a three-tier confidence system:

| Tier | Criteria | Weight | Headline? |
|------|----------|--------|-----------|
| 🟢 **Gold** | Target match, ≥15 clicks, has baseline sales | 100% | ✅ Yes |
| 🟡 **Silver** | Target/CST match, <15 clicks OR Ad Group fallback | 33-99% (scaled) | ✅ Yes (dampened) |
| 🔴 **Bronze** | <5 clicks, OR no baseline | 0% | ❌ Excluded |

### 2.2 Confidence Weight Calculation

```python
def compute_confidence_tier(row):
    """
    Computes confidence tier and weight for impact calculation.
    Called during Postgres impact computation.
    """
    # Gate 1: Validation (prerequisite)
    if row['validation_status'] == 'NOT IMPLEMENTED':
        return 'excluded', 0.0, 'not_implemented'
    
    # Gate 2: Data Quality
    # Bronze tier (excluded from headline)
    if row['before_clicks'] < 5:
        return 'bronze', 0.0, 'low_sample'
    if row['before_spend'] == 0:
        return 'bronze', 0.0, 'no_baseline'
    
    # Silver/Gold tier calculation
    weight = 1.0
    flags = []

    # PENALTY: Ad Group Fallback (New v3.3)
    # If we fell back to Ad Group data, confidence is halved
    if row['match_level'] == 'ad_group':
        weight *= 0.5
        flags.append('ad_group_fallback')
    
    # CST match dampening (85%)
    if row['match_level'] == 'cst':
        weight *= 0.85
        flags.append('cst_match')
    
    # Click-based dampening (5-15 clicks)
    if 5 <= row['before_clicks'] < 15:
        weight *= (row['before_clicks'] / 15.0)
        flags.append('mid_sample')
    
    # No baseline sales dampening (50%)
    if row['before_sales'] == 0:
        weight *= 0.5
        flags.append('no_baseline_sales')
    
    # Tier assignment
    if weight >= 0.85:
        return 'gold', weight, ','.join(flags) or 'clean'
    else:
        return 'silver', weight, ','.join(flags)
```

### 2.3 Match Level Hierarchy

Baseline data is sourced using a fallback chain:

| Priority | Match Level | Join Condition | Accuracy |
|----------|-------------|----------------|----------|
| 1 | **target** | `target_text + campaign + ad_group` | ✅ Highest |
| 2 | **cst** | `customer_search_term + campaign + ad_group` | ✅ Good |
| 3 | **ad_group** | `ad_group_name + campaign` | ⚠️ Imprecise (50% Penalty) |

```sql
-- Baseline matching logic (simplified)
COALESCE(
    target_stats.spend,      -- Priority 1: Target-level
    cst_stats.spend,         -- Priority 2: CST-level (negatives/harvests)
    ad_group_stats.spend     -- Priority 3: Ad Group fallback
) AS before_spend
```

---

## 3. Validation Status Definitions

### 3.1 Validation Priority

Validation is a **prerequisite gate** before data quality assessment:

```
Action Logged  →  Validation Check  →  Data Quality  →  Final Impact
                       │                    │
                  GATE 1              GATE 2
                       │                    │
                 Implemented?          Reliable?
```

### 3.2 Status Definitions

| Status | Meaning | Criteria | Impact Treatment |
|--------|---------|----------|------------------|
| **✓ CPC Validated** | Bid implemented correctly | Observed CPC within ±15% of suggested | Full tier weight |
| **✓ Directional** | Bid moved in expected direction | CPC changed >5% in intended direction | Full tier weight |
| **✓ Confirmed Blocked** | Negative eliminated spend | After Spend = $0 | Full weight (binary) |
| **✓ Spend Eliminated** | Bid down killed spend | BID_DOWN → After Spend = $0 | Full weight |
| **⚠️ NOT IMPLEMENTED** | Action not applied | No CPC movement, spend continued | **Impact = $0** |

---

## 4. Impact Formulas

### 4.1 Formula by Action Type

| Action Type | Formula | Notes |
|-------------|---------|-------|
| **BID_CHANGE** | `Actual_Sales - Expected_Sales` | Counterfactual model |
| **NEGATIVE** | `+Before_Spend` | Cost avoidance |
| **HARVEST** | `Realized_Sales - (Expected_Sales × 0.85)` | 15% efficiency decline factor |
| **SPEND_ELIMINATED** | `Δ_Sales - Δ_Spend` | Net profit change |

### 4.2 Counterfactual Model (Bid Changes)

```python
# Expected outcome if efficiency stayed constant
expected_clicks = after_spend / before_cpc
expected_sales = expected_clicks * baseline_spc  # 30-day rolling
decision_impact = actual_after_sales - expected_sales
```

### 4.3 Harvest Formula (v3.0 Clarification)

> **NOTE:** The PRD originally stated `+10% × Sales Lift`. This was superseded by the 0.85× counterfactual baseline in production. The PRD should be updated to reflect this.

**Current Implementation:**
```python
# Harvest assumes 15% efficiency decline when moving to exact match
counterfactual_baseline = source_expected_sales * 0.85
harvest_impact = realized_sales - counterfactual_baseline
```

**Rationale:** Historical analysis shows harvested keywords experience ~15% efficiency drop due to:
- Loss of broad/phrase match flexibility
- Competition with source campaign during transition
- Amazon attribution delays

---

## 5. Dashboard Changes

### 5.1 Headline Metrics

```
┌─────────────────────────────────────────────────────────────┐
│  Net Attributed Impact: +$12,450                            │
│  └─ Based on 847 actions (Gold + Silver tier)               │
│                                                             │
│  📊 Breakdown:                                              │
│     • Gold:   623 actions (74%)  — $9,230                  │
│     • Silver: 224 actions (26%)  — $3,220                  │
│                                                             │
│  ⚠️ Excluded from headline:                                │
│     • Bronze: 312 actions (27% of total)                   │
│       └─ 189 campaign fallback                             │
│       └─ 98 low sample (<5 clicks)                         │
│       └─ 25 no baseline                                    │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Diagnostics Page (New)

A new diagnostics page (`/impact_diagnostics`) provides:

1. **Dual-View Comparison:** Current Logic vs DB-Only values
2. **Divergence Analysis:** Summary diff panel highlighting mismatches
3. **Decision Outcome Map:** Scatter plot with quadrant classification
4. **Match Level Distribution:** Pie chart of target/cst/campaign matches

> **NOTE:** The diagnostics page is not linked in navigation. Access via direct URL only.

---

## 6. Guardrails

### 6.1 Low Sample (<5 clicks)

```python
if before_clicks < 5:
    final_decision_impact = 0
    confidence_tier = 'bronze'
```

### 6.2 ROAS Efficiency Capping

For medium-confidence targets (5-20 clicks):
```python
roas_cap = median_roas + 1 * std_dev_roas  # From high-confidence targets
if implied_roas > roas_cap:
    baseline_spc = capped_spc  # Prevent outlier inflation
```

### 6.3 Market Drag Exclusion

Actions classified as "Market Drag" (Market Down + Decision Down) are excluded from headline totals:

```python
# Summary calculation excludes Market Drag
total_impact = df[
    (df['is_mature'] == True) &
    (df['market_tag'] != 'Market Drag') &
    (~df['market_tag'].str.contains('Excluded', na=False))
]['final_decision_impact'].sum()
```

---

## 7. Migration Path

### Phase 1: Current (Diagnostic Only)
- Diagnostics page compares UI vs DB values
- No production changes

### Phase 2: UI Simplification
- Remove redundant calculations from `transforms.py`
- UI consumes `final_decision_impact` directly

### Phase 3: Confidence Tiering
- Add `confidence_tier`, `confidence_weight`, `match_level` to Postgres
- Update headline aggregation to use tiers

### Phase 4: SQLite Deprecation
- Remove SQLite impact logic from `db_manager.py`
- Single source of truth complete

---

## 8. File References

| Component | File Path | Status |
|-----------|-----------|--------|
| Impact Calculation | `core/postgres_manager.py` | ✅ Source of truth |
| UI Rendering | `features/impact/main.py` | ⚠️ Needs simplification |
| Data Transforms | `features/impact/data/transforms.py` | ⚠️ Has redundant calcs |
| Diagnostics | `features/impact/diagnostics.py` | 🔬 New (diagnostic mode) |
| SQLite (deprecated) | `core/db_manager.py` | ❌ To be deprecated |

---

## 9. Changelog

### February 9, 2026 (v3.3)
- **Strict Grouping:** Enforced Ad Group containment for all baseline lookups.
- **Fallback Logic:** Removed Campaign fallback; replaced with Ad Group fallback.
- **Confidence Penalty:** 50% weight reduction for actions using Ad Group fallback.

### February 5, 2026 (v3.0)
- **Confidence Tiering:** Three-tier system (Gold/Silver/Bronze)
- **Match Level Tracking:** Target → CST → Ad Group fallback chain
- **Diagnostics Page:** New standalone tool for DB vs UI comparison
- **Documentation:** Updated PRD Harvest formula, added this specification

### January 2026 (v2.1)
- **Confidence Weighting:** Linear dampening for 5-15 clicks
- **Maturity Fix:** Calendar days instead of report count
- **ROAS Capping:** Anti-outlier guardrail for medium-confidence

### December 2025 (v2.0)
- **Counterfactual Model:** Decision impact vs expected outcome
- **Multi-Horizon:** 14D/30D/60D measurement windows
- **Validation Layers:** CPC match, directional, normalized
