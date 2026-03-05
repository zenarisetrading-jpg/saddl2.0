# Market Drag Bug Fix

**Date:** February 5, 2026
**Issue:** Market Drag rows showing positive Impact values
**Severity:** High - Violates PRD methodology definition

---

## Problem Description

Users reported seeing **Market Drag** category labels with **positive Impact** values in the dashboard table. This violates the fundamental definition from the PRD:

### PRD Definition (Decision Outcome Matrix)

| Category | Expected Trend | Decision Value | Impact Sign |
|----------|---------------|----------------|-------------|
| Offensive Win | ≥ 0 | ≥ 0 | **Positive** |
| Defensive Win | < 0 | ≥ 0 | **Positive** |
| Gap | ≥ 0 | < 0 | **Negative** |
| **Market Drag** | **< 0** | **< 0** | **NEGATIVE** ✅ |

**By definition, Market Drag MUST have negative impact** because:
- Expected Trend < 0 (market was declining)
- Decision Value < 0 (you underperformed expectations)
- Therefore: Impact = Actual - Expected < Expected < Before → **NEGATIVE**

---

## Root Cause Analysis

### Investigation Steps

1. **SQL Query on PostgreSQL database** returned **zero** Market Drag rows with positive impact ✅
2. **Dashboard was showing** Market Drag rows with positive impact ❌
3. **Conclusion:** Bug is in the **dashboard display layer**, not database calculation

### The Bug

Located in `features/impact/data/transforms.py`, function `ensure_impact_columns()`:

**Original Code (Lines 45-76):**
```python
# Line 45: Calculate decision_impact from recalculated expected_sales
df['decision_impact'] = df['observed_after_sales'] - df['expected_sales']

# Lines 63-70: Assign market_tag based on THIS recalculated decision_impact
conditions = [
    (df['expected_trend_pct'] >= 0) & (df['decision_value_pct'] >= 0),
    (df['expected_trend_pct'] < 0) & (df['decision_value_pct'] >= 0),
    (df['expected_trend_pct'] >= 0) & (df['decision_value_pct'] < 0),
    (df['expected_trend_pct'] < 0) & (df['decision_value_pct'] < 0),
]
choices = ['Offensive Win', 'Defensive Win', 'Gap', 'Market Drag']
df['market_tag'] = np.select(conditions, choices, default='Unknown')

# Lines 74-76: THEN overwrite decision_impact with database value!
if 'final_decision_impact' in df.columns:
    df['decision_impact'] = df['final_decision_impact']  # ❌ MISMATCH!
```

**The Problem:**
1. `market_tag` is assigned based on **recalculated** `decision_impact` (line 70)
2. `decision_impact` is then **overwritten** with `final_decision_impact` from database (line 75)
3. These values can be **different**, creating the mismatch!

**Example Scenario:**
```
Recalculated: decision_impact = -5 → assigns market_tag = "Market Drag"
Database:     final_decision_impact = +10 → overwrites decision_impact = +10
Result:       Market Drag label with +10 impact ❌
```

---

## The Fix

**File:** `features/impact/data/transforms.py`
**Lines:** 52-90

### Solution Strategy

The database (`postgres_manager.py:2227`) **already calculates `market_tag` correctly** based on `final_decision_impact`. The dashboard should:

1. **Trust the database `market_tag`** when it exists (normal case)
2. **Only recalculate** for old cached data without `market_tag`
3. **Always copy `final_decision_impact` BEFORE calculating `market_tag`**

### Fixed Code

```python
# Check if database already provided market_tag
has_db_market_tag = 'market_tag' in df.columns and not df['market_tag'].isna().all()

if not has_db_market_tag:
    # Old cached data - need to calculate market_tag ourselves
    # Copy final_decision_impact FIRST if available
    if 'final_decision_impact' in df.columns:
        df['decision_impact'] = df['final_decision_impact']

    # NOW calculate market_tag based on FINAL values
    conditions = [...]
    df['market_tag'] = np.select(conditions, choices, default='Unknown')
else:
    # Database provided market_tag - use it!
    if 'final_decision_impact' in df.columns:
        df['decision_impact'] = df['final_decision_impact']
```

---

## Testing

**Test File:** `dev_resources/tests/test_market_drag_fix.py`

### Test Cases

1. **Database provides market_tag** (normal case)
   - ✅ Market Drag rows have negative impact

2. **Old cached data** (legacy case)
   - ✅ Market Drag calculated correctly with negative impact

3. **Category consistency check**
   - ✅ All Market Drag: negative impact
   - ✅ All Offensive/Defensive Win: positive impact
   - ✅ All Gap: negative impact

### Run Tests
```bash
cd /Users/zayaanyousuf/Documents/Amazon\ PPC/saddle/saddle/desktop
python3 dev_resources/tests/test_market_drag_fix.py
```

**Result:** ✅ ALL TESTS PASSED

---

## Verification Steps

1. **Restart the Streamlit app** to load the fixed code
2. **Navigate to Impact Dashboard** for `s2c_uae_test` account
3. **Filter to Market Drag** rows in the details table
4. **Verify:** All Market Drag rows now show **negative** Impact values

---

## Impact

### What Changed
- Dashboard now uses database `market_tag` values (already correct)
- Old cached data recalculates `market_tag` AFTER copying `final_decision_impact`
- Ensures category labels always match displayed Impact values

### What Didn't Change
- Database calculations (already correct)
- PRD methodology (no changes needed)
- Impact aggregation logic (already excludes Market Drag correctly)

### Files Modified
- `features/impact/data/transforms.py` (lines 52-90)

### Files Added
- `dev_resources/tests/test_market_drag_fix.py` (test suite)
- `dev_resources/documentation/MARKET_DRAG_BUG_FIX.md` (this document)

---

## Related Code Locations

| Component | File | Lines | Notes |
|-----------|------|-------|-------|
| **Database Calculation** | `core/postgres_manager.py` | 2220-2227 | ✅ Correct - uses final_decision_impact |
| **Dashboard Transform** | `features/impact/data/transforms.py` | 52-90 | ✅ Fixed - uses database market_tag |
| **Old Dashboard Code** | `features/impact_dashboard.py` | 34-101 | ⚠️ Deprecated function (still used in some places) |
| **Table Display** | `features/impact/components/tables.py` | 38 | Renames market_tag → "Category" |

---

## Future Improvements

1. **Remove `_ensure_impact_columns` from `impact_dashboard.py`**
   - Already replaced by cleaner version in `impact/data/transforms.py`
   - Still being called in a few places (lines 453, 942, 1345, 2707)

2. **Add database constraint**
   - Postgres CHECK constraint: `market_tag = 'Market Drag' → final_decision_impact <= 0`
   - Prevents this bug at the source

3. **Add dashboard validation**
   - Assert no Market Drag rows with positive impact before rendering
   - Fail fast if data inconsistency detected

---

## Additional Fix: HARVEST 0.85x Counterfactual

### Issue
Database was using **fixed 10% attribution** for HARVEST instead of **0.85x counterfactual** documented in HARVEST_LOGIC.md.

### Fix Applied
Updated `core/postgres_manager.py` to use counterfactual formula:
- **Lines 1737-1748:** Removed fixed 10% attribution
- **Lines 2147-2153:** Added 0.85x factor to expected_sales for HARVEST
- **Lines 2162-2177:** Removed HARVEST from special_types_mask (now uses standard counterfactual)

**Formula:**
```python
expected_sales = (observed_after_spend / cpc_before) * spc_before * 0.85
decision_impact = observed_after_sales - expected_sales
```

**Example:**
- Source: $400 sales, $100 spend (4.0x ROAS)
- Exact: $900 sales, $200 spend
- Expected (0.85x): $200 / $2 CPC × $8 SPC × 0.85 = $680
- **Impact: $900 - $680 = +$220** (vs old $40 with 10%)

### Test Coverage
Added `dev_resources/tests/test_harvest_085x.py`:
- ✅ Verifies 0.85x formula matches HARVEST_LOGIC.md
- ✅ Confirms failed harvests can have negative impact
- ✅ Compares new vs old logic

---

## Conclusion

✅ **Bug Fixed:** Market Drag can no longer show positive Impact values
✅ **HARVEST Logic Updated:** Now uses 0.85x counterfactual (not fixed 10%)
✅ **Tests Pass:** All test cases verify correct behavior
✅ **PRD Compliant:** Dashboard and database both match methodology definition

The fix ensures **database is single source of truth** with correct HARVEST calculations, and dashboard **displays without recalculation**, eliminating all mismatches between category labels and displayed Impact values.
