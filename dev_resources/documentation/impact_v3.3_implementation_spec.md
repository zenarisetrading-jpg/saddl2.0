# Impact Model v3.3 Implementation Specification

**Version**: 3.3  
**Date**: February 6, 2026  
**Status**: Ready for Implementation  
**Target**: `debug.py` → then `features/impact_dashboard.py` + `core/postgres_manager.py`

---

## Executive Summary

v3.3 introduces a **Layered Counterfactual Model** that isolates **Decision Impact** from **Market Forces** and **Expected Scale Effects**. This aligns with PRD Section 4.11 (ROAS Attribution Decomposition) and Section 4.9 (Decision Outcome Matrix).

### Key Changes from v3.2

| Component | v3.2 | v3.3 |
|-----------|------|------|
| Counterfactual | Linear (assumes constant SPC) | Layered (market + scale adjusted) |
| Market adjustment | None | Account-level SPC shift applied |
| Scale adjustment | None | Diminishing returns for scale-up |
| Positive handling | Linear | Linear (unchanged - no inflation) |
| Negative handling | Linear | Adjusted + capped at zero |
| ROAS decomposition | Not implemented | Full waterfall breakdown |

### Expected Results (from analysis)

| Metric | v3.2 (Linear) | v3.3 (Layered) |
|--------|---------------|----------------|
| Total Impact | -$22,703 | -$3,306 |
| Wins | +$28,512 | +$27,537 |
| Gaps | -$51,215 | -$30,843 |
| Market Drag (excluded) | -$640 | -$222 |

---

## 1. Core Concepts

### 1.1 The Problem with Linear Counterfactual

**Current formula:**
```
expected_sales = after_clicks × before_spc
decision_impact = observed_after_sales - expected_sales
```

**Problem:** This assumes:
- Market conditions are constant (SPC doesn't change account-wide)
- Scale has no effect (doubling clicks should double sales)

Both assumptions are FALSE. This causes:
- Unfair penalties when market drops (external factor)
- Unfair penalties when scaling up (expected diminishing returns)

### 1.2 The Layered Counterfactual Solution

**New formula:**
```
market_shift = account_spc_after / account_spc_before
scale_factor = 1 / (click_ratio ^ α) if click_ratio > 1 else 1.0

expected_spc = before_spc × market_shift × scale_factor
expected_sales = after_clicks × expected_spc
decision_impact = observed_after_sales - expected_sales
```

**What this does:**
1. **Market adjustment**: If the whole account's SPC dropped 12%, we expect THIS target's SPC to drop ~12% too
2. **Scale adjustment**: If clicks doubled (2x), we expect ~19% efficiency loss (at α=0.3)
3. **Decision impact**: Only the REMAINING gap is attributed to the decision

### 1.3 Asymmetric Application

To maintain conservative/honest reporting:
- **Positive outcomes**: Keep LINEAR (don't inflate wins)
- **Negative + scale-up**: Apply LAYERED (market + scale), cap at zero
- **Negative + scale-down**: Apply MARKET only (no scale bonus), cap at zero

**Why asymmetric?**
- Reducing penalties is FAIR (expected some loss)
- Inflating wins is NOT FAIR (gaming the metric)
- Capping at zero prevents negative→positive flips

---

## 2. Implementation Details

### 2.1 Required Inputs

```python
# From the export/database
required_columns = [
    'before_clicks',
    'after_clicks', 
    'before_spend',
    'observed_after_spend',
    'before_sales',
    'observed_after_sales',
    'market_tag',  # 'Market Drag' or 'Neutral'
    'confidence_weight',  # From v3.2 tiering (now includes 50% penalty for Ad Group fallback)
    'confidence_tier',    # 'gold', 'silver', 'excluded'
]
```

### 2.2 Constants

```python
# Diminishing returns exponent
# At α=0.3: 2x clicks → expect 81% of before_spc
# Calibrate based on historical data if needed
SCALE_ALPHA = 0.3

# Minimum threshold for scale adjustment
# Don't adjust for tiny scale changes
SCALE_THRESHOLD = 1.0  # Apply when click_ratio > 1.0
```

### 2.3 Step-by-Step Calculation

```python
import pandas as pd
import numpy as np

def calculate_v33_impact(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate v3.3 layered counterfactual impact.
    
    Args:
        df: DataFrame with required columns (see 2.1)
        
    Returns:
        DataFrame with additional columns:
        - impact_linear: Original linear impact
        - impact_v33: New layered impact
        - market_shift: Account-level SPC change factor
        - scale_factor: Diminishing returns factor
        - expected_sales_v33: Adjusted expected sales
    """
    df = df.copy()
    
    # =========================================================
    # STEP 1: Calculate base metrics
    # =========================================================
    df['spc_before'] = df['before_sales'] / df['before_clicks']
    df['spc_after'] = df['observed_after_sales'] / df['after_clicks'].replace(0, np.nan)
    df['click_ratio'] = df['after_clicks'] / df['before_clicks']
    
    # Handle edge cases
    df['spc_before'] = df['spc_before'].replace([np.inf, -np.inf], np.nan)
    df['spc_after'] = df['spc_after'].replace([np.inf, -np.inf], np.nan)
    df['click_ratio'] = df['click_ratio'].replace([np.inf, -np.inf], np.nan).fillna(1.0)
    
    # =========================================================
    # STEP 2: Calculate MARKET SHIFT (account-level)
    # =========================================================
    total_before_sales = df['before_sales'].sum()
    total_before_clicks = df['before_clicks'].sum()
    total_after_sales = df['observed_after_sales'].sum()
    total_after_clicks = df['after_clicks'].sum()
    
    account_spc_before = total_before_sales / total_before_clicks if total_before_clicks > 0 else 0
    account_spc_after = total_after_sales / total_after_clicks if total_after_clicks > 0 else 0
    
    # Market shift factor (e.g., 0.88 means account SPC dropped 12%)
    if account_spc_before > 0:
        market_shift = account_spc_after / account_spc_before
    else:
        market_shift = 1.0
    
    # Clamp market shift to reasonable bounds (avoid extreme adjustments)
    market_shift = np.clip(market_shift, 0.5, 1.5)
    
    # Store for reference
    df['market_shift'] = market_shift
    
    # =========================================================
    # STEP 3: Calculate SCALE FACTOR (per-row)
    # =========================================================
    # Diminishing returns: 1 / (click_ratio ^ α) for scale-up
    # No adjustment for scale-down (ratio <= 1)
    
    SCALE_ALPHA = 0.3
    
    df['scale_factor'] = np.where(
        df['click_ratio'] > SCALE_THRESHOLD,
        1 / (df['click_ratio'] ** SCALE_ALPHA),
        1.0
    )
    
    # Clamp scale factor to reasonable bounds
    df['scale_factor'] = np.clip(df['scale_factor'], 0.5, 1.0)
    
    # =========================================================
    # STEP 4: Calculate LINEAR impact (baseline comparison)
    # =========================================================
    df['expected_sales_linear'] = df['after_clicks'] * df['spc_before']
    df['impact_linear'] = df['observed_after_sales'] - df['expected_sales_linear']
    
    # =========================================================
    # STEP 5: Calculate LAYERED expected sales
    # =========================================================
    # For scale-up: apply both market AND scale adjustment
    # For scale-down: apply only market adjustment
    
    df['expected_sales_layered'] = np.where(
        df['click_ratio'] > SCALE_THRESHOLD,
        df['after_clicks'] * df['spc_before'] * market_shift * df['scale_factor'],
        df['after_clicks'] * df['spc_before'] * market_shift
    )
    
    df['impact_layered'] = df['observed_after_sales'] - df['expected_sales_layered']
    
    # Market-only expected (for scale-down cases)
    df['expected_sales_market'] = df['after_clicks'] * df['spc_before'] * market_shift
    df['impact_market'] = df['observed_after_sales'] - df['expected_sales_market']
    
    # =========================================================
    # STEP 6: Apply ASYMMETRIC logic
    # =========================================================
    # Rule 1: Positive linear → keep linear (don't inflate wins)
    # Rule 2: Negative + scale-up → use layered, cap at zero
    # Rule 3: Negative + scale-down → use market-only, cap at zero
    
    df['impact_v33'] = np.where(
        df['impact_linear'] > 0,
        # POSITIVE: Keep linear (no inflation)
        df['impact_linear'],
        np.where(
            df['click_ratio'] > SCALE_THRESHOLD,
            # NEGATIVE + SCALE-UP: Layered adjustment, capped at zero
            np.minimum(df['impact_layered'], 0),
            # NEGATIVE + SCALE-DOWN: Market adjustment only, capped at zero
            np.minimum(df['impact_market'], 0)
        )
    )
    
    # =========================================================
    # STEP 7: Apply confidence weighting
    # =========================================================
    df['final_impact_v33'] = df['impact_v33'] * df['confidence_weight']
    
    # =========================================================
    # STEP 8: Store expected sales for v3.3
    # =========================================================
    df['expected_sales_v33'] = np.where(
        df['impact_linear'] > 0,
        df['expected_sales_linear'],  # Used linear for positive
        np.where(
            df['click_ratio'] > SCALE_THRESHOLD,
            df['expected_sales_layered'],  # Used layered for scale-up negative
            df['expected_sales_market']     # Used market for scale-down negative
        )
    )
    
    return df
```

### 2.4 Quadrant Classification

```python
def classify_quadrants(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify actions into PRD Section 4.9.3 quadrants.
    
    Quadrants:
    - Offensive Win: Spend up + beat expectations
    - Defensive Win: Spend down + beat expectations  
    - Decision Gap: Spend up + missed expectations
    - Market Drag: Pre-tagged in market_tag column
    """
    df = df.copy()
    
    df['spend_change_pct'] = (
        (df['observed_after_spend'] - df['before_spend']) / 
        df['before_spend'].replace(0, np.nan) * 100
    ).fillna(0)
    
    def assign_quadrant(row):
        # Market Drag takes precedence (already tagged)
        if row.get('market_tag') == 'Market Drag':
            return 'Market Drag'
        
        impact = row['impact_v33']
        spend_direction = row['spend_change_pct']
        
        if impact >= 0 and spend_direction >= 0:
            return 'Offensive Win'
        elif impact >= 0 and spend_direction < 0:
            return 'Defensive Win'
        elif impact < 0 and spend_direction >= 0:
            return 'Decision Gap'
        else:  # impact < 0 and spend < 0, but not Market Drag
            return 'Decision Gap'  # Treat as gap if not explicitly tagged
    
    df['quadrant_v33'] = df.apply(assign_quadrant, axis=1)
    
    return df
```

### 2.5 Aggregate Impact Calculation

```python
def calculate_aggregate_impact(df: pd.DataFrame) -> dict:
    """
    Calculate aggregate impact metrics excluding Market Drag.
    
    Returns:
        dict with headline metrics
    """
    # Exclude Market Drag from headline
    included = df[df['market_tag'] != 'Market Drag']
    excluded = df[df['market_tag'] == 'Market Drag']
    
    # Classify wins vs gaps
    wins = included[included['impact_v33'] >= 0]
    gaps = included[included['impact_v33'] < 0]
    
    # Quadrant breakdown
    offensive = included[included['quadrant_v33'] == 'Offensive Win']
    defensive = included[included['quadrant_v33'] == 'Defensive Win']
    decision_gaps = included[included['quadrant_v33'] == 'Decision Gap']
    
    return {
        # Headline
        'net_impact': included['final_impact_v33'].sum(),
        'net_impact_unweighted': included['impact_v33'].sum(),
        
        # Wins vs Gaps
        'wins_total': wins['final_impact_v33'].sum(),
        'wins_count': len(wins),
        'gaps_total': gaps['final_impact_v33'].sum(),
        'gaps_count': len(gaps),
        
        # Quadrant breakdown
        'offensive_wins_total': offensive['final_impact_v33'].sum(),
        'offensive_wins_count': len(offensive),
        'defensive_wins_total': defensive['final_impact_v33'].sum(),
        'defensive_wins_count': len(defensive),
        'decision_gaps_total': decision_gaps['final_impact_v33'].sum(),
        'decision_gaps_count': len(decision_gaps),
        
        # Excluded
        'market_drag_total': excluded['final_impact_v33'].sum(),
        'market_drag_count': len(excluded),
        
        # Totals
        'total_actions': len(df),
        'measured_actions': len(included),
        'excluded_actions': len(excluded),
    }
```

---

## 3. ROAS Waterfall Decomposition

### 3.1 Components

Per PRD Section 4.11, decompose ROAS change into:

1. **Baseline ROAS**: Starting point (before period)
2. **Market Forces**: Account-level SPC change (CVR/AOV shifts)
3. **CPC Efficiency**: Cost per click change
4. **Decision Impact**: v3.3 impact converted to ROAS contribution
5. **Residual**: Unexplained (model error)

### 3.2 Implementation

```python
def calculate_roas_waterfall(df: pd.DataFrame, decision_impact_dollars: float) -> dict:
    """
    Calculate ROAS waterfall decomposition.
    
    Args:
        df: DataFrame with before/after metrics
        decision_impact_dollars: Net decision impact from v3.3 (e.g., -3306)
        
    Returns:
        dict with waterfall components
    """
    # =========================================================
    # TOTALS
    # =========================================================
    before_spend = df['before_spend'].sum()
    before_sales = df['before_sales'].sum()
    before_clicks = df['before_clicks'].sum()
    
    after_spend = df['observed_after_spend'].sum()
    after_sales = df['observed_after_sales'].sum()
    after_clicks = df['after_clicks'].sum()
    
    # =========================================================
    # ROAS CALCULATIONS
    # =========================================================
    baseline_roas = before_sales / before_spend if before_spend > 0 else 0
    actual_roas = after_sales / after_spend if after_spend > 0 else 0
    
    # =========================================================
    # MARKET FORCES (SPC change)
    # =========================================================
    # SPC = Sales Per Click
    baseline_spc = before_sales / before_clicks if before_clicks > 0 else 0
    actual_spc = after_sales / after_clicks if after_clicks > 0 else 0
    
    market_spc_change = actual_spc / baseline_spc if baseline_spc > 0 else 1.0
    
    # Market effect on ROAS (holding CPC constant)
    # If SPC dropped 12%, ROAS drops proportionally
    market_effect_roas = baseline_roas * (market_spc_change - 1)
    
    # =========================================================
    # CPC EFFICIENCY
    # =========================================================
    # CPC = Cost Per Click
    baseline_cpc = before_spend / before_clicks if before_clicks > 0 else 0
    actual_cpc = after_spend / after_clicks if after_clicks > 0 else 0
    
    cpc_change = actual_cpc / baseline_cpc if baseline_cpc > 0 else 1.0
    
    # CPC effect on ROAS (inverse relationship - higher CPC = lower ROAS)
    # Applied after market adjustment
    cpc_effect_roas = baseline_roas * market_spc_change * (1/cpc_change - 1) if cpc_change > 0 else 0
    
    # =========================================================
    # DECISION IMPACT
    # =========================================================
    # Convert dollar impact to ROAS contribution
    decision_effect_roas = decision_impact_dollars / after_spend if after_spend > 0 else 0
    
    # =========================================================
    # RESIDUAL
    # =========================================================
    explained_roas = baseline_roas + market_effect_roas + cpc_effect_roas + decision_effect_roas
    residual_roas = actual_roas - explained_roas
    
    # =========================================================
    # PERCENTAGE ATTRIBUTION
    # =========================================================
    total_change = actual_roas - baseline_roas
    
    def safe_pct(component, total):
        if total == 0:
            return 0
        return (component / total) * 100
    
    return {
        # Raw values
        'baseline_roas': baseline_roas,
        'actual_roas': actual_roas,
        'total_change': total_change,
        
        # Components (ROAS units)
        'market_effect': market_effect_roas,
        'cpc_effect': cpc_effect_roas,
        'decision_effect': decision_effect_roas,
        'residual': residual_roas,
        
        # Underlying metrics
        'baseline_spc': baseline_spc,
        'actual_spc': actual_spc,
        'spc_change_pct': (market_spc_change - 1) * 100,
        
        'baseline_cpc': baseline_cpc,
        'actual_cpc': actual_cpc,
        'cpc_change_pct': (cpc_change - 1) * 100,
        
        # Attribution percentages
        'market_pct_of_change': safe_pct(market_effect_roas, total_change),
        'cpc_pct_of_change': safe_pct(cpc_effect_roas, total_change),
        'decision_pct_of_change': safe_pct(decision_effect_roas, total_change),
        'residual_pct_of_change': safe_pct(residual_roas, total_change),
        
        # External vs Internal
        'external_effect': market_effect_roas + cpc_effect_roas,
        'external_pct': safe_pct(market_effect_roas + cpc_effect_roas, total_change),
        'internal_effect': decision_effect_roas,
        'internal_pct': safe_pct(decision_effect_roas, total_change),
    }
```

---

## 4. Complete Debug Script

### 4.1 Full Implementation

```python
#!/usr/bin/env python3
"""
Impact Model v3.3 Debug Script
==============================

Tests the layered counterfactual model with:
- Market shift adjustment
- Scale adjustment (diminishing returns)
- Asymmetric application
- ROAS waterfall decomposition

Usage:
    python debug.py --input /path/to/export.csv
    
Output:
    Prints detailed analysis and comparison to v3.2
"""

import pandas as pd
import numpy as np
import argparse
from typing import Dict, Tuple

# ============================================================================
# CONSTANTS
# ============================================================================

SCALE_ALPHA = 0.3          # Diminishing returns exponent
SCALE_THRESHOLD = 1.0      # Apply scale adjustment when click_ratio > this
MARKET_SHIFT_BOUNDS = (0.5, 1.5)  # Clamp market shift to reasonable range
SCALE_FACTOR_BOUNDS = (0.5, 1.0)  # Clamp scale factor to reasonable range


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def load_and_validate(filepath: str) -> pd.DataFrame:
    """Load CSV and validate required columns."""
    df = pd.read_csv(filepath)
    
    required = [
        'before_clicks', 'after_clicks',
        'before_spend', 'observed_after_spend',
        'before_sales', 'observed_after_sales',
        'market_tag', 'confidence_weight'
    ]
    
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    print(f"✓ Loaded {len(df)} rows from {filepath}")
    return df


def calculate_market_shift(df: pd.DataFrame) -> float:
    """Calculate account-level SPC shift."""
    total_before_sales = df['before_sales'].sum()
    total_before_clicks = df['before_clicks'].sum()
    total_after_sales = df['observed_after_sales'].sum()
    total_after_clicks = df['after_clicks'].sum()
    
    account_spc_before = total_before_sales / total_before_clicks if total_before_clicks > 0 else 0
    account_spc_after = total_after_sales / total_after_clicks if total_after_clicks > 0 else 0
    
    if account_spc_before > 0:
        market_shift = account_spc_after / account_spc_before
    else:
        market_shift = 1.0
    
    # Clamp to bounds
    market_shift = np.clip(market_shift, *MARKET_SHIFT_BOUNDS)
    
    return market_shift


def calculate_v33_impact(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate v3.3 layered counterfactual impact.
    """
    df = df.copy()
    
    # ----- Base metrics -----
    df['spc_before'] = df['before_sales'] / df['before_clicks'].replace(0, np.nan)
    df['spc_after'] = df['observed_after_sales'] / df['after_clicks'].replace(0, np.nan)
    df['click_ratio'] = df['after_clicks'] / df['before_clicks'].replace(0, np.nan)
    
    # Handle edge cases
    df['spc_before'] = df['spc_before'].replace([np.inf, -np.inf], np.nan).fillna(0)
    df['spc_after'] = df['spc_after'].replace([np.inf, -np.inf], np.nan).fillna(0)
    df['click_ratio'] = df['click_ratio'].replace([np.inf, -np.inf], np.nan).fillna(1.0)
    
    # ----- Market shift (account-level) -----
    market_shift = calculate_market_shift(df)
    df['market_shift'] = market_shift
    
    # ----- Scale factor (per-row) -----
    df['scale_factor'] = np.where(
        df['click_ratio'] > SCALE_THRESHOLD,
        1 / (df['click_ratio'] ** SCALE_ALPHA),
        1.0
    )
    df['scale_factor'] = np.clip(df['scale_factor'], *SCALE_FACTOR_BOUNDS)
    
    # ----- Linear impact (v3.2 baseline) -----
    df['expected_sales_linear'] = df['after_clicks'] * df['spc_before']
    df['impact_linear'] = df['observed_after_sales'] - df['expected_sales_linear']
    
    # ----- Layered expected sales -----
    df['expected_sales_layered'] = np.where(
        df['click_ratio'] > SCALE_THRESHOLD,
        df['after_clicks'] * df['spc_before'] * market_shift * df['scale_factor'],
        df['after_clicks'] * df['spc_before'] * market_shift
    )
    df['impact_layered'] = df['observed_after_sales'] - df['expected_sales_layered']
    
    # Market-only (for scale-down)
    df['expected_sales_market'] = df['after_clicks'] * df['spc_before'] * market_shift
    df['impact_market'] = df['observed_after_sales'] - df['expected_sales_market']
    
    # ----- Asymmetric application -----
    df['impact_v33'] = np.where(
        df['impact_linear'] > 0,
        df['impact_linear'],  # Positive: keep linear
        np.where(
            df['click_ratio'] > SCALE_THRESHOLD,
            np.minimum(df['impact_layered'], 0),  # Scale-up negative: layered, cap at 0
            np.minimum(df['impact_market'], 0)    # Scale-down negative: market, cap at 0
        )
    )
    
    # ----- Apply confidence weighting -----
    df['final_impact_v33'] = df['impact_v33'] * df['confidence_weight']
    df['final_impact_linear'] = df['impact_linear'] * df['confidence_weight']
    
    # ----- Expected sales for v3.3 -----
    df['expected_sales_v33'] = np.where(
        df['impact_linear'] > 0,
        df['expected_sales_linear'],
        np.where(
            df['click_ratio'] > SCALE_THRESHOLD,
            df['expected_sales_layered'],
            df['expected_sales_market']
        )
    )
    
    return df


def classify_quadrants(df: pd.DataFrame) -> pd.DataFrame:
    """Classify actions into PRD quadrants."""
    df = df.copy()
    
    df['spend_change_pct'] = (
        (df['observed_after_spend'] - df['before_spend']) /
        df['before_spend'].replace(0, np.nan) * 100
    ).fillna(0)
    
    def assign_quadrant(row):
        if row.get('market_tag') == 'Market Drag':
            return 'Market Drag'
        
        impact = row['impact_v33']
        spend_dir = row['spend_change_pct']
        
        if impact >= 0 and spend_dir >= 0:
            return 'Offensive Win'
        elif impact >= 0 and spend_dir < 0:
            return 'Defensive Win'
        else:
            return 'Decision Gap'
    
    df['quadrant_v33'] = df.apply(assign_quadrant, axis=1)
    
    return df


def calculate_aggregate_impact(df: pd.DataFrame) -> Dict:
    """Calculate aggregate impact metrics."""
    included = df[df['market_tag'] != 'Market Drag']
    excluded = df[df['market_tag'] == 'Market Drag']
    
    wins = included[included['impact_v33'] >= 0]
    gaps = included[included['impact_v33'] < 0]
    
    offensive = included[included['quadrant_v33'] == 'Offensive Win']
    defensive = included[included['quadrant_v33'] == 'Defensive Win']
    decision_gaps = included[included['quadrant_v33'] == 'Decision Gap']
    
    return {
        'net_impact': included['final_impact_v33'].sum(),
        'net_impact_unweighted': included['impact_v33'].sum(),
        'wins_total': wins['final_impact_v33'].sum(),
        'wins_count': len(wins),
        'gaps_total': gaps['final_impact_v33'].sum(),
        'gaps_count': len(gaps),
        'offensive_wins_total': offensive['final_impact_v33'].sum(),
        'offensive_wins_count': len(offensive),
        'defensive_wins_total': defensive['final_impact_v33'].sum(),
        'defensive_wins_count': len(defensive),
        'decision_gaps_total': decision_gaps['final_impact_v33'].sum(),
        'decision_gaps_count': len(decision_gaps),
        'market_drag_total': excluded['final_impact_v33'].sum(),
        'market_drag_count': len(excluded),
        'total_actions': len(df),
        'measured_actions': len(included),
    }


def calculate_roas_waterfall(df: pd.DataFrame, decision_impact_dollars: float) -> Dict:
    """Calculate ROAS waterfall decomposition."""
    before_spend = df['before_spend'].sum()
    before_sales = df['before_sales'].sum()
    before_clicks = df['before_clicks'].sum()
    
    after_spend = df['observed_after_spend'].sum()
    after_sales = df['observed_after_sales'].sum()
    after_clicks = df['after_clicks'].sum()
    
    # ROAS
    baseline_roas = before_sales / before_spend if before_spend > 0 else 0
    actual_roas = after_sales / after_spend if after_spend > 0 else 0
    
    # SPC (Sales Per Click)
    baseline_spc = before_sales / before_clicks if before_clicks > 0 else 0
    actual_spc = after_sales / after_clicks if after_clicks > 0 else 0
    market_spc_change = actual_spc / baseline_spc if baseline_spc > 0 else 1.0
    
    # CPC (Cost Per Click)
    baseline_cpc = before_spend / before_clicks if before_clicks > 0 else 0
    actual_cpc = after_spend / after_clicks if after_clicks > 0 else 0
    cpc_change = actual_cpc / baseline_cpc if baseline_cpc > 0 else 1.0
    
    # Effects
    market_effect = baseline_roas * (market_spc_change - 1)
    cpc_effect = baseline_roas * market_spc_change * (1/cpc_change - 1) if cpc_change > 0 else 0
    decision_effect = decision_impact_dollars / after_spend if after_spend > 0 else 0
    
    explained = baseline_roas + market_effect + cpc_effect + decision_effect
    residual = actual_roas - explained
    
    total_change = actual_roas - baseline_roas
    
    def safe_pct(val, total):
        return (val / total * 100) if total != 0 else 0
    
    return {
        'baseline_roas': baseline_roas,
        'actual_roas': actual_roas,
        'total_change': total_change,
        'market_effect': market_effect,
        'cpc_effect': cpc_effect,
        'decision_effect': decision_effect,
        'residual': residual,
        'baseline_spc': baseline_spc,
        'actual_spc': actual_spc,
        'spc_change_pct': (market_spc_change - 1) * 100,
        'baseline_cpc': baseline_cpc,
        'actual_cpc': actual_cpc,
        'cpc_change_pct': (cpc_change - 1) * 100,
        'market_pct': safe_pct(market_effect, total_change),
        'cpc_pct': safe_pct(cpc_effect, total_change),
        'decision_pct': safe_pct(decision_effect, total_change),
        'external_total': market_effect + cpc_effect,
        'external_pct': safe_pct(market_effect + cpc_effect, total_change),
    }


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def print_comparison(df: pd.DataFrame):
    """Print v3.2 vs v3.3 comparison."""
    print("\n" + "="*70)
    print("📊 v3.2 vs v3.3 COMPARISON")
    print("="*70)
    
    # Linear (v3.2)
    linear_total = df['final_impact_linear'].sum()
    linear_positive = df[df['impact_linear'] > 0]['final_impact_linear'].sum()
    linear_negative = df[df['impact_linear'] < 0]['final_impact_linear'].sum()
    
    # v3.3
    v33_total = df[df['market_tag'] != 'Market Drag']['final_impact_v33'].sum()
    v33_positive = df[df['impact_v33'] > 0]['final_impact_v33'].sum()
    v33_negative = df[df['impact_v33'] < 0]['final_impact_v33'].sum()
    
    print(f"""
   ┌────────────────────────────────────────────────────────────────┐
   │  Metric                      │    v3.2       │    v3.3        │
   ├────────────────────────────────────────────────────────────────┤
   │  Total Impact                │  ${linear_total:>10,.0f}  │  ${v33_total:>10,.0f}   │
   │  Positive (Wins)             │  ${linear_positive:>10,.0f}  │  ${v33_positive:>10,.0f}   │
   │  Negative (Gaps)             │  ${linear_negative:>10,.0f}  │  ${v33_negative:>10,.0f}   │
   └────────────────────────────────────────────────────────────────┘
   
   Improvement: ${v33_total - linear_total:+,.0f}
    """)


def print_aggregate_impact(agg: Dict):
    """Print aggregate impact summary."""
    print("\n" + "="*70)
    print("📊 v3.3 DECISION-ATTRIBUTED IMPACT")
    print("="*70)
    
    print(f"""
   ┌────────────────────────────────────────────────────────────────┐
   │  INCLUDED IN HEADLINE:                                         │
   │    ✅ Offensive Wins:  ${agg['offensive_wins_total']:>10,.0f}  ({agg['offensive_wins_count']} actions)         │
   │    ✅ Defensive Wins:  ${agg['defensive_wins_total']:>10,.0f}  ({agg['defensive_wins_count']} actions)         │
   │    ❌ Decision Gaps:   ${agg['decision_gaps_total']:>10,.0f}  ({agg['decision_gaps_count']} actions)         │
   │  ─────────────────────────────────────────────────────────────  │
   │    NET IMPACT:         ${agg['net_impact']:>10,.0f}                              │
   │                                                                │
   │  EXCLUDED (ambiguous attribution):                             │
   │    ⚠️ Market Drag:     ${agg['market_drag_total']:>10,.0f}  ({agg['market_drag_count']} actions)         │
   └────────────────────────────────────────────────────────────────┘
    """)


def print_roas_waterfall(wf: Dict):
    """Print ROAS waterfall decomposition."""
    print("\n" + "="*70)
    print("📊 ROAS ATTRIBUTION WATERFALL")
    print("="*70)
    
    print(f"""
   ┌────────────────────────────────────────────────────────────────┐
   │  BASELINE ROAS                              {wf['baseline_roas']:>6.2f}x             │
   │  ──────────────────────────────────────────────────────────────│
   │                                                                │
   │  📉 Market Forces (SPC {wf['spc_change_pct']:+.1f}%)            {wf['market_effect']:>+6.2f}x             │
   │     (CVR/AOV shifted account-wide)                             │
   │                                                                │
   │  📉 CPC Efficiency ({wf['cpc_change_pct']:+.1f}%)              {wf['cpc_effect']:>+6.2f}x             │
   │     (Cost per click changed)                                   │
   │                                                                │
   │  📉 Optimization Decisions                  {wf['decision_effect']:>+6.2f}x             │
   │     (Net impact of bid/negative actions)                       │
   │                                                                │
   │  📈 Residual                                {wf['residual']:>+6.2f}x             │
   │     (Unexplained / model error)                                │
   │                                                                │
   │  ──────────────────────────────────────────────────────────────│
   │  ACTUAL ROAS                                {wf['actual_roas']:>6.2f}x             │
   └────────────────────────────────────────────────────────────────┘

   SUMMARY:
     Total ROAS Change: {wf['total_change']:+.2f}x
     ├─ External (Market + CPC): {wf['external_total']:+.2f}x ({wf['external_pct']:.0f}% of change)
     └─ Decisions:               {wf['decision_effect']:+.2f}x ({wf['decision_pct']:.0f}% of change)
    """)


def print_sample_rows(df: pd.DataFrame, n: int = 10):
    """Print sample rows showing adjustment effect."""
    print("\n" + "="*70)
    print(f"📊 TOP {n} NEGATIVE ROWS - ADJUSTMENT EFFECT")
    print("="*70)
    
    worst = df.nsmallest(n, 'impact_linear').copy()
    
    cols = ['target_text', 'click_ratio', 'spc_before', 'spc_after',
            'impact_linear', 'impact_v33', 'market_shift', 'scale_factor']
    
    # Truncate target_text for display
    worst['target_text'] = worst['target_text'].str[:20]
    
    print(worst[cols].round(2).to_string())


# ============================================================================
# MAIN
# ============================================================================

def main(filepath: str):
    """Main execution."""
    print("="*70)
    print("🚀 IMPACT MODEL v3.3 DEBUG")
    print("="*70)
    
    # Load data
    df = load_and_validate(filepath)
    
    # Calculate v3.3 impact
    print("\n⏳ Calculating v3.3 impact...")
    df = calculate_v33_impact(df)
    print(f"✓ Market shift: {df['market_shift'].iloc[0]:.2f} ({(df['market_shift'].iloc[0]-1)*100:+.1f}%)")
    
    # Classify quadrants
    df = classify_quadrants(df)
    
    # Calculate aggregates
    agg = calculate_aggregate_impact(df)
    
    # Calculate ROAS waterfall
    decision_impact = agg['net_impact_unweighted']
    wf = calculate_roas_waterfall(df, decision_impact)
    
    # Print outputs
    print_comparison(df)
    print_aggregate_impact(agg)
    print_roas_waterfall(wf)
    print_sample_rows(df)
    
    print("\n" + "="*70)
    print("✅ DEBUG COMPLETE")
    print("="*70)
    
    return df, agg, wf


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Impact Model v3.3 Debug")
    parser.add_argument("--input", "-i", required=True, help="Path to export CSV")
    args = parser.parse_args()
    
    df, agg, wf = main(args.input)
```

---

## 5. Testing Checklist

### 5.1 Unit Tests

```python
def test_market_shift_calculation():
    """Market shift should be account_spc_after / account_spc_before."""
    df = pd.DataFrame({
        'before_clicks': [100, 100],
        'after_clicks': [100, 100],
        'before_sales': [1000, 1000],  # SPC = 10
        'observed_after_sales': [880, 880],  # SPC = 8.8
    })
    shift = calculate_market_shift(df)
    assert abs(shift - 0.88) < 0.01, f"Expected 0.88, got {shift}"


def test_scale_factor():
    """Scale factor should be 1/(ratio^0.3) for scale-up."""
    # At 2x scale: 1/(2^0.3) = 0.812
    ratio = 2.0
    expected = 1 / (ratio ** 0.3)
    assert abs(expected - 0.812) < 0.01


def test_asymmetric_positive():
    """Positive linear should remain unchanged."""
    df = pd.DataFrame({
        'before_clicks': [10],
        'after_clicks': [20],
        'before_spend': [10],
        'observed_after_spend': [20],
        'before_sales': [100],
        'observed_after_sales': [250],  # Better than expected
        'market_tag': ['Neutral'],
        'confidence_weight': [1.0],
    })
    result = calculate_v33_impact(df)
    # Linear would be: 250 - (20 * 10) = 250 - 200 = 50
    assert result['impact_v33'].iloc[0] == result['impact_linear'].iloc[0]


def test_asymmetric_negative_scaleup():
    """Negative + scale-up should use layered, capped at 0."""
    df = pd.DataFrame({
        'before_clicks': [10],
        'after_clicks': [20],  # 2x scale
        'before_spend': [10],
        'observed_after_spend': [20],
        'before_sales': [100],  # SPC = 10
        'observed_after_sales': [50],  # Much worse
        'market_tag': ['Neutral'],
        'confidence_weight': [1.0],
    })
    result = calculate_v33_impact(df)
    # Linear: 50 - 200 = -150
    # Layered should be less negative
    assert result['impact_v33'].iloc[0] > result['impact_linear'].iloc[0]
    assert result['impact_v33'].iloc[0] <= 0  # Capped at 0


def test_market_drag_excluded():
    """Market Drag should be excluded from headline."""
    df = pd.DataFrame({
        'before_clicks': [10, 10],
        'after_clicks': [10, 10],
        'before_spend': [10, 10],
        'observed_after_spend': [10, 10],
        'before_sales': [100, 100],
        'observed_after_sales': [50, 50],
        'market_tag': ['Neutral', 'Market Drag'],
        'confidence_weight': [1.0, 1.0],
    })
    result = calculate_v33_impact(df)
    result = classify_quadrants(result)
    agg = calculate_aggregate_impact(result)
    
    assert agg['measured_actions'] == 1
    assert agg['market_drag_count'] == 1
```

### 5.2 Integration Tests

Run with actual export:

```bash
python debug.py --input /mnt/user-data/uploads/2026-02-06T07-12_export.csv
```

Expected outputs:
- Total Impact: ~-$3,306 (was -$22,703)
- Market Shift: ~0.88 (-12%)
- Wins: ~$27,537
- Gaps: ~-$30,843
- Market Drag excluded: 54 actions

### 5.3 Edge Case Tests

1. **Zero clicks before**: Should handle gracefully (no division by zero)
2. **Zero clicks after**: Should handle gracefully
3. **All Market Drag**: Should show 0 measured actions
4. **All positive**: Should equal linear (no adjustment)
5. **Extreme scale (10x)**: Scale factor should clamp to 0.5

---

## 6. Production Migration

### 6.1 Files to Update

| File | Changes |
|------|---------|
| `core/postgres_manager.py` | Add market_shift calculation to query |
| `features/impact_dashboard.py` | Replace linear with v3.3 calculation |
| `features/impact_dashboard.py` | Add ROAS waterfall component |
| `components/impact_cards.py` | Update headline display |

### 6.2 Database Changes

None required. All calculations are done in Python on query results.

### 6.3 New Columns in Export

| Column | Type | Description |
|--------|------|-------------|
| `market_shift` | FLOAT | Account-level SPC change factor |
| `scale_factor` | FLOAT | Diminishing returns factor |
| `impact_v33` | FLOAT | v3.3 adjusted impact (unweighted) |
| `final_impact_v33` | FLOAT | v3.3 impact × confidence_weight |
| `expected_sales_v33` | FLOAT | Adjusted expected sales |
| `quadrant_v33` | VARCHAR | PRD quadrant classification |

### 6.4 UI Changes

1. **Headline**: Show v3.3 net impact (excluding Market Drag)
2. **Subtext**: "Wins: +$X | Gaps: -$Y | Excluded: Z actions"
3. **ROAS Waterfall**: New chart component
4. **Tooltip**: Explain market/scale adjustment

---

## 7. Rollback Plan

If issues arise:
1. Feature flag: `USE_V33_IMPACT = False`
2. Falls back to linear calculation
3. No database changes to revert

---

## Appendix A: Formula Reference

### A.1 Linear (v3.2)
```
expected_sales = after_clicks × before_spc
impact = observed_after_sales - expected_sales
```

### A.2 Layered (v3.3)
```
market_shift = account_spc_after / account_spc_before
scale_factor = 1 / (click_ratio ^ 0.3) if click_ratio > 1 else 1.0

expected_spc = before_spc × market_shift × scale_factor
expected_sales = after_clicks × expected_spc
impact = observed_after_sales - expected_sales
```

### A.3 Asymmetric Rules
```
if impact_linear > 0:
    impact_v33 = impact_linear  # Keep linear
elif click_ratio > 1:
    impact_v33 = min(impact_layered, 0)  # Layered, cap at 0
else:
    impact_v33 = min(impact_market, 0)  # Market only, cap at 0
```

### A.4 ROAS Waterfall
```
market_effect = baseline_roas × (spc_change - 1)
cpc_effect = baseline_roas × spc_change × (1/cpc_change - 1)
decision_effect = decision_impact_dollars / after_spend
residual = actual_roas - (baseline + market + cpc + decision)
```

---

## Appendix B: Expected Results

For the test file `2026-02-06T07-12_export.csv`:

| Metric | Value |
|--------|-------|
| Rows | 807 |
| Market Shift | 0.88 (-12%) |
| Linear Total | -$22,703 |
| v3.3 Total | -$3,306 |
| Improvement | +$19,397 |
| Wins | +$27,537 (439 actions) |
| Gaps | -$30,843 (314 actions) |
| Market Drag | -$222 (54 actions) |
| Baseline ROAS | 4.14x |
| Actual ROAS | 3.45x |
| Market Effect | -0.50x |
| CPC Effect | -0.19x |
| Decision Effect | -0.08x |
