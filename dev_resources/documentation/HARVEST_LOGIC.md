# Harvest Logic Reference

**Version:** 2.0  
**Last Updated:** February 4, 2026  
**Change Origin:** Harvest Logic Refinement (v2.0)

This document describes the complete harvest logic for keyword promotion from discovery campaigns (Auto, Broad, Phrase) to exact match campaigns.

---

## 1. Overview

The harvest process promotes high-performing search terms from discovery campaigns to dedicated exact match campaigns. This allows for precise bid control and improved ROAS on proven winners.

### Key Components
| Component | Description | Location |
|-----------|-------------|----------|
| **Selection Logic** | Identifies harvest candidates | `optimizer/strategies/harvest.py` |
| **Launch Multiplier** | Bid boost for new keywords | `optimizer/core.py` |
| **Impact Calculation** | Counterfactual performance measurement | `core/db_manager.py` |
| **Dashboard Display** | Market tag categorization | `features/impact_dashboard.py` |

---

## 2. Selection Criteria

A search term qualifies for harvest if it meets ALL of the following:

### 2.1 Source Requirements
- Must originate from a **Discovery Campaign** (Auto, Broad, or Phrase match)
- Cannot already exist as an **Exact Match** keyword in any campaign

### 2.2 Performance Thresholds
| Metric | Minimum | Rationale |
|--------|---------|-----------|
| **Orders** | ≥ 3 | Ensures conversion consistency |
| **Clicks** | ≥ 10 | Statistical reliability |
| **ROAS** | ≥ Baseline × HARVEST_ROAS_MULT | Profitability filter |

### 2.3 ROAS Baseline Logic
```python
# Dynamic threshold based on account performance
if term_roas >= universal_median_roas:
    threshold = universal_median_roas * HARVEST_ROAS_MULT
else:
    threshold = baseline_roas * HARVEST_ROAS_MULT

# Default HARVEST_ROAS_MULT = 1.0 (match baseline)
```

---

## 3. Launch Multiplier (1.75x)

### 3.1 Purpose
New exact match keywords often experience "Ghost Rate" - they receive zero impressions due to low initial bids losing all auctions.

### 3.2 Implementation
```python
# In optimizer/core.py
HARVEST_LAUNCH_MULTIPLIER = 1.75

# Applied in results.py when generating bulk file
suggested_bid = winner_cpc * HARVEST_LAUNCH_MULTIPLIER
```

### 3.3 Effect
| Metric | Before | After (1.75x) |
|--------|--------|---------------|
| Winner CPC | $1.00 | $1.75 |
| Expected Ghost Rate | ~40% | ~15% |
| Auction Win Rate | Low | Competitive |

> **Note**: This is a **forward-looking** adjustment only. It does NOT retroactively affect existing keywords.

---

## 4. Impact Calculation (0.85x Counterfactual)

### 4.1 Philosophy
We measure harvest impact against what would have happened if we did nothing, assuming a natural 15% efficiency decline.

### 4.2 Why 0.85x?
Historical analysis shows harvested keywords typically lose ~15% efficiency when moved to exact match due to:
1. Loss of broad/phrase match flexibility
2. Competition with the source campaign during transition
3. Amazon's attribution delays (7-14 days)

### 4.3 Formula
```python
# In db_manager.py - get_action_impact()

# Step 1: Get Source Performance
source_roas = before_sales / before_spend

# Step 2: Calculate Expected Performance (85% of source)
expected_roas = source_roas * 0.85
expected_sales = realized_spend * expected_roas

# Step 3: Calculate Impact (value above baseline)
if realized_sales > 0:
    impact_score = realized_sales - expected_sales
else:
    impact_score = 0.0  # No credit for Ghosts
```

### 4.4 Example Calculation
| Metric | Value |
|--------|-------|
| **Source Spend (Before)** | $100 |
| **Source Sales (Before)** | $400 |
| **Source ROAS** | 4.0x |
| **Expected ROAS (0.85x)** | 3.4x |
| **Realized Spend (After)** | $200 |
| **Realized Sales (After)** | $900 |
| **Expected Sales** | $200 × 3.4 = $680 |
| **Impact Score** | $900 - $680 = **+$220** |

### 4.5 Dashboard Categorization
The `impact_dashboard.py` uses the same 0.85x factor for consistent market tag assignment:

| Category | Criteria | Meaning |
|----------|----------|---------|
| **Offensive Win** | expected_trend ≥ 0, decision_value ≥ 0 | Growth + Beat expectations |
| **Defensive Win** | expected_trend < 0, decision_value ≥ 0 | Decline but beat expectations |
| **Gap** | expected_trend ≥ 0, decision_value < 0 | Growth but missed expectations |
| **Market Drag** | expected_trend < 0, decision_value < 0 | Decline + missed expectations |

---

## 5. Validation Statuses

| Status | Criteria | Impact Treatment |
|--------|----------|------------------|
| **✓ Harvested (migrated)** | Source spend = $0 | Full impact credit |
| **✓ Harvested (90%+ blocked)** | Source spend dropped ≥90% | Full impact credit |
| **✓ Harvested (partial)** | Destination has sales | Proportional credit |
| **⚠️ Ghost (0 Sales)** | Destination sales = $0 | Impact = 0 |

---

## 6. Code Locations

| Function | File | Line Range |
|----------|------|------------|
| `identify_harvest_candidates` | `strategies/harvest.py` | 50-180 |
| `HARVEST_LAUNCH_MULTIPLIER` | `core.py` | 15-20 |
| `get_action_impact` (HARVEST branch) | `db_manager.py` | 1373-1405 |
| `_ensure_impact_columns` | `impact_dashboard.py` | 34-83 |

---

## 7. Test Coverage

Unit tests are located in `dev_resources/tests/test_harvest_impact_logic.py`:

| Test Case | Description |
|-----------|-------------|
| `test_harvest_winner` | Verifies +$220 impact for outperforming keyword |
| `test_harvest_baseline` | Verifies $0 impact for exactly meeting 0.85x baseline |
| `test_harvest_ghost` | Verifies $0 impact and "Ghost" status for no-show keywords |

Run tests:
```bash
cd /path/to/saddle/desktop
python -m pytest dev_resources/tests/test_harvest_impact_logic.py -v
```

---

## 8. Change Log

| Date | Version | Change |
|------|---------|--------|
| Feb 4, 2026 | 2.0 | Implemented 0.85x counterfactual baseline, 1.75x launch multiplier |
| Jan 2026 | 1.0 | Original 10% lift attribution model |
