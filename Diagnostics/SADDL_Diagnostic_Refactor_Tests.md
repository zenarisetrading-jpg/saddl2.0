# SADDL Diagnostic v2.0 Refactor — Test Plan & Guardrails

**Version:** Refactor Edition  
**Date:** February 2026  
**Scope:** Redesign existing diagnostic module (no database changes)

---

## 1. Refactor Scope

### What's Changing

**Files Being Modified:**
```
features/diagnostics/
├── control_center.py         ← NEW (replaces overview.py, signals.py, trends.py)
├── styles.py                 ← MODIFIED (enhanced CSS)
└── __init__.py               ← MODIFIED (new imports)

utils/
└── diagnostics.py            ← MODIFIED (new functions added)

components/
└── diagnostic_cards.py       ← MODIFIED (new components)

ppcsuite_v4_ui_experiment.py  ← MODIFIED (routing change)
```

**Files Being Deprecated:**
```
features/diagnostics/
├── overview.py               ← DELETE (replaced by control_center.py)
├── signals.py                ← DELETE (replaced by control_center.py)
└── trends.py                 ← DELETE (replaced by control_center.py)
```

### What's NOT Changing

❌ **Database Schema**
- No new tables
- No schema migrations
- Only new SELECT queries

❌ **Other App Pages**
- Campaigns page unchanged
- Targets page unchanged
- Impact Dashboard unchanged

❌ **Data Pipelines**
- BSR pipeline unchanged
- Aggregator unchanged
- No backfills needed

---

## 2. Guardrails (Simplified)

### ALLOWED Operations

✅ **Modify diagnostic module files**
- features/diagnostics/*.py
- components/diagnostic_cards.py
- utils/diagnostics.py (add new functions only)

✅ **New SELECT queries**
- Read from sc_raw.*
- Read from sc_analytics.*
- Read from public.raw_search_term_data (read-only)
- Read from public.actions_log (read-only via get_impact_summary)

✅ **CSS modifications**
- Enhance features/diagnostics/styles.py
- Add new glassmorphic styles

### FORBIDDEN Operations

❌ **Do NOT modify these files:**
- app_core/postgres_manager.py
- pipeline/*.py (BSR, aggregator, runner)
- db/migrations/*.sql
- features/impact/*.py
- features/optimizer/*.py
- features/bids_tab.py, harvest_tab.py, negatives_tab.py

❌ **Do NOT modify database:**
- No CREATE TABLE
- No ALTER TABLE
- No INSERT/UPDATE/DELETE
- No DROP anything

❌ **Do NOT modify existing functions:**
- Don't change signatures of existing functions in utils/diagnostics.py
- Only ADD new functions

---

## 3. Test Plan (12 Tests)

### Pre-Refactor Tests (Run BEFORE changes)

**Test 1: Baseline Functionality**
```bash
# Verify existing app works
streamlit run ppcsuite_v4_ui_experiment.py

# Navigate to each page:
# - Campaigns ✓
# - Targets ✓
# - Impact Dashboard ✓
# - Diagnostics (old version) ✓

# All should load without errors
```

**Test 2: Baseline Performance**
```python
# Measure current diagnostic page load time
python3 -c "
import time
from utils.diagnostics import get_diagnostics_overview_payload

start = time.time()
payload = get_diagnostics_overview_payload('s2c_uae_test')
print(f'Baseline: {time.time() - start:.2f}s')
"

# Record baseline time
```

---

### Post-Refactor Tests (Run AFTER changes)

#### Group A: Core Intelligence Tests

**Test 3: Health Score Computation**
```python
python3 -c "
from utils.diagnostics import compute_health_score

health = compute_health_score('s2c_uae_test', days=30)

assert 0 <= health['score'] <= 100, 'Score out of range'
assert health['status'] in ['HEALTHY', 'CAUTION', 'DECLINING', 'CRITICAL']
assert all(k in health for k in ['sales_score', 'tacos_score', 'organic_score', 'bsr_score'])

print('✅ Health score computes correctly')
print(f'Score: {health[\"score\"]}/100, Status: {health[\"status\"]}')
"
```

**Test 4: Root Cause Attribution**
```python
python3 -c "
from utils.diagnostics import diagnose_root_causes

diagnosis = diagnose_root_causes('s2c_uae_test', days=30)

# Attribution should sum to ~100%
total = diagnosis['organic_decay_pct'] + diagnosis['market_demand_pct'] + diagnosis['optimization_lift_pct']
assert 0 <= total <= 110, f'Attribution sum {total}% out of range'

# Should have evidence
assert 'bsr_change' in diagnosis
assert 'cvr_correlation' in diagnosis

print('✅ Root cause attribution works')
print(f'Organic: {diagnosis[\"organic_decay_pct\"]}%, Market: {diagnosis[\"market_demand_pct\"]}%, Optimization: {diagnosis[\"optimization_lift_pct\"]}%')
"
```

**Test 5: Recommendations Generation**
```python
python3 -c "
from utils.diagnostics import compute_health_score, diagnose_root_causes, generate_recommendations

health = compute_health_score('s2c_uae_test', days=30)
diagnosis = diagnose_root_causes('s2c_uae_test', days=30)
recommendations = generate_recommendations(diagnosis, health)

assert isinstance(recommendations, list), 'Should return list'
assert len(recommendations) > 0, 'Should have at least one recommendation'

for rec in recommendations:
    assert all(k in rec for k in ['priority', 'icon', 'action', 'reason', 'severity'])

print('✅ Recommendations generated')
print(f'Generated {len(recommendations)} recommendations')
for rec in recommendations[:3]:
    print(f'  - {rec[\"priority\"]}: {rec[\"action\"]}')
"
```

**Test 6: Impact Dashboard Integration**
```python
python3 -c "
from utils.diagnostics import diagnose_root_causes

diagnosis = diagnose_root_causes('s2c_uae_test', days=30)

# Should include Impact Dashboard metrics
assert 'optimization_win_rate' in diagnosis
assert 'optimization_impact' in diagnosis

print('✅ Impact Dashboard integration working')
print(f'Win rate: {diagnosis[\"optimization_win_rate\"]:.0f}%')
print(f'Avg impact: {diagnosis[\"optimization_impact\"]:+.1f}pts')
"
```

#### Group B: Correlation Intelligence Tests

**Test 7: BSR-ROAS Correlation**
```python
python3 -c "
from utils.diagnostics import compute_bsr_roas_correlation

bsr_roas = compute_bsr_roas_correlation(days=60)

assert 'correlation' in bsr_roas
assert 'dates' in bsr_roas
assert 'interpretation' in bsr_roas
assert len(bsr_roas['dates']) > 0, 'Should have data points'

print('✅ BSR-ROAS correlation computed')
print(f'Correlation: r = {bsr_roas[\"correlation\"]:.2f}')
print(f'Data points: {len(bsr_roas[\"dates\"])}')
"
```

**Test 8: CVR Divergence Detection**
```python
python3 -c "
from utils.diagnostics import detect_cvr_divergence

cvr_div = detect_cvr_divergence(days=60)

assert 'correlation' in cvr_div
assert 'diagnosis' in cvr_div
assert 'detail' in cvr_div

print('✅ CVR divergence detection working')
print(f'Correlation: r = {cvr_div[\"correlation\"]:.2f}')
print(f'Diagnosis: {cvr_div[\"diagnosis\"]}')
"
```

#### Group C: ASIN Intelligence Tests

**Test 9: ASIN Action Table**
```python
python3 -c "
from utils.diagnostics import get_asin_action_table

asin_table = get_asin_action_table(days=30)

assert isinstance(asin_table, list), 'Should return list'
# May be empty if no ASINs meet criteria, that's OK

if len(asin_table) > 0:
    asin = asin_table[0]
    assert all(k in asin for k in ['asin', 'priority', 'action', 'monthly_impact'])
    print(f'✅ ASIN table generated ({len(asin_table)} ASINs)')
else:
    print('⚠️  ASIN table empty (no ASINs meet criteria)')
"
```

#### Group D: UI Integration Tests

**Test 10: Control Center Page Loads**
```bash
# Start app
streamlit run ppcsuite_v4_ui_experiment.py &
sleep 5

# Visit in browser:
# Navigate to Diagnostics
# Should see new Control Center (not old 3-page tabs)
# Should load without errors

# Expected:
# - Health Score card visible
# - 3 Root Cause cards visible
# - 2 Correlation charts visible
# - ASIN table visible

# Manual verification required
```

**Test 11: Glassmorphic Design Applied**
```
Browser Developer Tools → Inspect Element

Verify CSS classes present:
- .health-card
- .cause-card
- .metric-mini
- .asin-table

Verify glassmorphic effects:
- backdrop-filter: blur(...)
- background: linear-gradient with rgba
- border: 1-4px solid rgba(255, 255, 255, ...)

Visual check:
- Cards have frosted glass effect
- Dark theme applied
- No default Streamlit styling visible
```

#### Group E: Regression Tests

**Test 12: Existing Pages Still Work**
```bash
# Navigate to each existing page:
# - Campaigns
# - Targets  
# - Impact Dashboard

# All should load without errors
# No console errors in browser
# No Python errors in terminal

# Verify:
✓ Campaigns page loads
✓ Targets page loads
✓ Impact Dashboard loads
✓ Navigation works
✓ No 500 errors
```

---

## 4. Performance Benchmarks

**Acceptance Criteria:**

| Metric | Target | Critical Threshold |
|---|---|---|
| Health score computation | <2s | <5s |
| Root cause diagnosis | <3s | <8s |
| Control center page load | <5s | <10s |
| BSR-ROAS correlation | <2s | <5s |
| ASIN table generation | <3s | <8s |

**Test Command:**
```python
python3 -c "
import time
from utils.diagnostics import (
    compute_health_score,
    diagnose_root_causes,
    compute_bsr_roas_correlation,
    get_asin_action_table
)

tests = [
    ('Health score', lambda: compute_health_score('s2c_uae_test', 30)),
    ('Root cause', lambda: diagnose_root_causes('s2c_uae_test', 30)),
    ('BSR-ROAS corr', lambda: compute_bsr_roas_correlation(60)),
    ('ASIN table', lambda: get_asin_action_table(30))
]

print('Performance Benchmarks:')
for name, func in tests:
    start = time.time()
    func()
    duration = time.time() - start
    status = '✅' if duration < 5 else '⚠️'
    print(f'{status} {name}: {duration:.2f}s')
"
```

---

## 5. Rollback Procedure

### If Refactor Breaks Something

**Option 1: Git Revert (Recommended)**
```bash
# Check current commit
git log --oneline -5

# Revert to before refactor
git revert <commit_hash>

# Or reset to previous commit (destructive)
git reset --hard HEAD~1

# Restart app
streamlit run ppcsuite_v4_ui_experiment.py
```

**Option 2: Manual Rollback**
```bash
# Restore old files from git
git checkout HEAD~1 -- features/diagnostics/
git checkout HEAD~1 -- utils/diagnostics.py
git checkout HEAD~1 -- components/diagnostic_cards.py
git checkout HEAD~1 -- ppcsuite_v4_ui_experiment.py

# Restart app
streamlit run ppcsuite_v4_ui_experiment.py
```

**Option 3: Keep Both Versions**
```python
# In ppcsuite_v4_ui_experiment.py, add toggle:

if st.sidebar.checkbox("Use New Diagnostics", value=True):
    from features.diagnostics.control_center import render_control_center
    render_control_center(client_id)
else:
    # Old version
    from features.diagnostics.overview import render_overview_page
    render_overview_page(client_id)
```

---

## 6. Validation Checklist

**Before declaring refactor complete:**

```
□ All 12 tests pass
□ Performance benchmarks within targets
□ Existing pages still work (Campaigns, Targets, Impact Dashboard)
□ Glassmorphic design visually confirmed
□ Health score displays correctly
□ Root cause attribution sums to ~100%
□ Recommendations generated
□ Charts render with interpretations
□ ASIN table populates (or shows "no ASINs" message)
□ Impact Dashboard integration shows win rate
□ No console errors in browser
□ No Python errors in terminal
□ Page load time acceptable
```

---

## 7. Known Issues & Workarounds

### Issue 1: ASIN-Level Paid Data Missing

**Problem:** `get_asin_action_table()` needs ASIN-level paid ROAS, but `raw_search_term_data` doesn't have ASIN column.

**Workaround:** Show NULL or account-level ROAS in table until Ads API integration adds ASIN attribution.

**Code:**
```python
# In get_asin_action_table():
paid_roas = NULL::NUMERIC as paid_roas  # Placeholder
```

**Future fix:** Phase 2 Ads API integration will add ASIN-level ad data.

---

### Issue 2: Impact Dashboard Empty

**Problem:** `get_impact_summary()` returns all zeros if no recent actions in `actions_log`.

**Workaround:** Show "No recent optimization actions" message instead of errors.

**Code:**
```python
if diagnosis['optimization_win_rate'] == 0:
    # Show message instead of breaking
    return {
        'priority': 'INFO',
        'icon': 'ℹ️',
        'action': 'No recent optimizations to validate',
        'reason': 'Start logging optimization actions in Impact Dashboard'
    }
```

---

### Issue 3: BSR Data Sparse for Some ASINs

**Problem:** Some ASINs return 404 from Catalog API (discontinued products).

**Expected:** Normal behavior, already handled in BSR pipeline.

**Impact:** Those ASINs won't appear in ASIN table (correct behavior).

---

## 8. Success Criteria Summary

**Refactor is successful when:**

✅ **Intelligence works**
- Answers "why" not just shows data
- Clear diagnosis and recommendations
- Attribution percentages logical

✅ **Integration works**  
- Impact Dashboard data flows in
- BSR correlates with ROAS
- CVR divergence detected

✅ **Design works**
- Glassmorphic styling visible
- Dark theme professional
- Single-page layout clean

✅ **No regressions**
- Existing pages still work
- No new errors
- Performance acceptable

---

*Refactor test plan v1.0 — lightweight validation for diagnostic redesign*
