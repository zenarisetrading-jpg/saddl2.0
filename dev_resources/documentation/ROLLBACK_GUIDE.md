# Impact Model v3.3 → v3.2 Rollback Guide

## Overview

This guide provides step-by-step instructions for rolling back from Impact Model v3.3 to v3.2 if issues arise in production.

**Rollback Time:** < 5 minutes
**Data Loss:** None (all v3.2 calculations preserved in backup columns)
**Reversibility:** 100% reversible

---

## Quick Rollback (Production Emergency)

If you need to rollback immediately:

### Step 1: Change Feature Flag

**File:** `core/postgres_manager.py` (line ~99)

```python
# FROM:
IMPACT_MODEL_VERSION = "v3.3"  # Options: "v3.3" | "v3.2"

# TO:
IMPACT_MODEL_VERSION = "v3.2"  # Options: "v3.3" | "v3.2"
```

### Step 2: Restart Application

```bash
# If using Streamlit Cloud
git add core/postgres_manager.py
git commit -m "ROLLBACK: Revert to Impact Model v3.2"
git push origin main

# If running locally
# Just save the file - Streamlit will auto-reload
```

### Step 3: Verify Rollback

1. Open Impact & Results dashboard
2. Look for version indicator (should show "v3.2" instead of "v3.3")
3. Verify impact calculations match previous v3.2 values
4. Export data and confirm `model_version` column shows "v3.2"

**That's it!** The feature flag ensures instant rollback with zero data migration.

---

## What Happens During Rollback

### Automatic Changes

When `IMPACT_MODEL_VERSION = "v3.2"`:

1. **get_action_impact()** bypasses v3.3 calculations
2. Uses original v3.2 linear impact logic
3. No new columns added (market_shift, scale_factor, impact_v33)
4. Dashboard displays v3.2 calculations

### Preserved Data

During v3.3 execution, v3.2 values were backed up to:
- `decision_impact_v32`: Original v3.2 impact
- `final_decision_impact_v32`: Original v3.2 weighted impact

These columns remain available for comparison even after rollback.

---

## Rollback Validation Checklist

After rollback, verify these items:

- [ ] Dashboard shows "v3.2" in hero banner
- [ ] Total impact matches previous v3.2 baseline
- [ ] No errors in dashboard rendering
- [ ] Export shows `model_version: v3.2`
- [ ] No v3.3-specific columns causing errors
- [ ] Wins/Gaps/Drag counts match v3.2 expectations

---

## Rollback Scenarios

### Scenario 1: Dashboard Errors

**Symptoms:**
- Errors on Impact Dashboard
- Missing columns
- Calculation exceptions

**Action:**
1. Immediate rollback to v3.2
2. Check logs for specific error
3. Report issue with error traceback

### Scenario 2: Unexpected Impact Values

**Symptoms:**
- Impact values don't match stakeholder expectations
- Win rate drastically different from v3.2
- Metrics seem wrong

**Action:**
1. Export data with both v3.2 and v3.3 columns
2. Compare `final_decision_impact` vs `final_decision_impact_v32`
3. Identify specific actions causing discrepancy
4. Rollback if confidence lost
5. Investigate root cause offline

### Scenario 3: Performance Issues

**Symptoms:**
- Dashboard loads slowly
- Timeouts on impact calculations
- High database CPU

**Action:**
1. Rollback to v3.2 immediately
2. Profile v3.3 calculations offline
3. Optimize before redeploying

---

## Re-enabling v3.3 After Rollback

Once issues are resolved:

### Step 1: Fix Root Cause

Address the issue that caused rollback:
- Fix bugs in `_calculate_v33_impact_columns()`
- Update validation logic
- Optimize performance
- Clarify stakeholder expectations

### Step 2: Test Offline

```bash
cd /Users/zayaanyousuf/Documents/Amazon\ PPC/saddle/saddle/desktop
python dev_resources/tests/test_v33_edge_cases.py
python test_v33_with_real_data.py
```

### Step 3: Gradual Re-enable

```python
# In postgres_manager.py
IMPACT_MODEL_VERSION = "v3.3"  # Options: "v3.3" | "v3.2"
```

### Step 4: Monitor

- Watch dashboard for 24 hours
- Compare v3.3 vs v3.2 backup columns
- Validate with stakeholders
- Monitor performance metrics

---

## Technical Details

### Feature Flag Implementation

The rollback is implemented via a simple conditional in `get_action_impact()`:

```python
if IMPACT_MODEL_VERSION == "v3.3":
    # Calculate v3.3 impact with market + scale adjustments
    df = self._calculate_v33_impact_columns(df)

    # Backup v3.2 values
    df['decision_impact_v32'] = df['decision_impact'].copy()
    df['final_decision_impact_v32'] = df['final_decision_impact'].copy()

    # Replace with v3.3 values
    df['decision_impact'] = df['impact_v33']
    df['final_decision_impact'] = df['final_impact_v33']
    df['expected_sales'] = df['expected_sales_v33']
else:
    # Use v3.2 calculations as-is
    pass
```

### Backup Columns

These columns are ONLY created when v3.3 is active:

| Column | Description |
|--------|-------------|
| `decision_impact_v32` | v3.2 linear impact (backup) |
| `final_decision_impact_v32` | v3.2 weighted impact (backup) |
| `market_shift` | v3.3 account-level SPC adjustment |
| `scale_factor` | v3.3 per-row scale efficiency |
| `impact_v33` | v3.3 unweighted impact |
| `final_impact_v33` | v3.3 final weighted impact |
| `expected_sales_v33` | v3.3 expected sales |

### No Data Migration Required

Rollback is instant because:
1. v3.2 calculations never removed
2. Feature flag switches logic path
3. No database schema changes
4. No data deletion

---

## Comparison Reports

To generate v3.2 vs v3.3 comparison:

### While v3.3 is Active:

```python
import pandas as pd
from core.db_manager import get_db_manager

db = get_db_manager()
df = db.get_action_impact(client_id="YOUR_CLIENT_ID", before_days=14, after_days=14)

# Compare columns
comparison = df[[
    'action_date',
    'target_text',
    'action_type',
    'final_decision_impact',      # v3.3 value
    'final_decision_impact_v32',  # v3.2 backup
    'market_shift',
    'scale_factor'
]].copy()

comparison['difference'] = comparison['final_decision_impact'] - comparison['final_decision_impact_v32']
comparison['pct_change'] = (comparison['difference'] / comparison['final_decision_impact_v32'].abs() * 100).fillna(0)

# Export for analysis
comparison.to_csv('v32_v33_comparison.csv', index=False)
```

---

## Rollback Decision Matrix

| Issue | Severity | Rollback? | Timeline |
|-------|----------|-----------|----------|
| Dashboard won't load | 🔴 Critical | YES | Immediate |
| Calculation errors | 🔴 Critical | YES | Immediate |
| Performance degradation (>30s load) | 🟡 High | YES | Within 1 hour |
| Impact values "feel wrong" | 🟡 High | MAYBE | Investigate first |
| Stakeholder confusion | 🟢 Low | NO | Training/docs |
| Minor discrepancies (<5%) | 🟢 Low | NO | Expected behavior |

---

## Contact & Support

If rollback doesn't resolve the issue:

1. Check logs: `streamlit run app.py --logger.level=debug`
2. Review recent commits: `git log --oneline -10`
3. Restore from backup: `git checkout core/postgres_manager.py.bak`
4. Report issue with:
   - Error traceback
   - Screenshots
   - Export data showing problem
   - Steps to reproduce

---

## Version History

| Date | Version | Change |
|------|---------|--------|
| 2026-02-07 | v3.3 | Layered counterfactual with market + scale |
| 2025-XX-XX | v3.2 | Linear impact with confidence weighting |

---

## Appendix: Code Locations

Key files for rollback:

```
core/postgres_manager.py
├── Line 99: IMPACT_MODEL_VERSION flag
├── Line 1529: _calculate_v33_impact_columns()
└── Line 2473: Feature flag check

features/impact/main.py
├── Line 18: Import export utils
└── Line 258: Version consistency check

features/impact/utils/export_utils.py
└── Export with version tracking

features/impact/components/hero.py
└── Line 146: Version badge display
```

---

**Last Updated:** 2026-02-07
**Status:** Production Ready ✅
