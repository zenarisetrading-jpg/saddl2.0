# SADDL Diagnostic Tool — Claude Code Handoff Checklist
## Complete Package Ready for Implementation

**Date:** February 18, 2026  
**Status:** Ready for Execution  
**Estimated Build Time:** 5 weeks (3 phases)

---

## 1. Documentation Package (Complete ✅)

You have **5 complete documents** ready for Claude Code:

### 1.1 Core Specifications

**📄 SADDL_Diagnostics_PRD_v2.md**
- Feature requirements for diagnostic tool
- 5 signal detection patterns with complete SQL
- UI wireframes for 3 pages
- Integration with existing Impact Dashboard
- Success metrics and acceptance criteria
- **Status:** ✅ Complete, reviewed, ready

**📄 SADDL_Backend_Architecture.md**
- Three-schema isolation design
- Complete table schemas with indexes
- Connection management (pooler vs direct)
- Query patterns and performance optimization
- Migration system and rollback procedures
- **Status:** ✅ Complete, comprehensive

**📄 SADDL_Frontend_Architecture.md**
- Complete glassmorphic design system
- 20+ custom SVG icons (no bitmap emojis)
- Component library (cards, buttons, tables)
- Full CSS specifications
- Responsive design patterns
- **Status:** ✅ Complete, production-ready

### 1.2 Safety & Guardrails

**📄 SADDL_Implementation_Guardrails.md**
- Database write boundaries (DO NOT TOUCH public schema)
- File system boundaries (what to create/modify)
- Test requirements (26+ test cases)
- Validation gates (3 phase checkpoints)
- Rollback procedures
- Code review checklists
- **Status:** ✅ Complete, enforceable

**📄 SADDL_Context_Variables.md**
- Exact table names from your database
- Impact Dashboard integration patterns
- Existing code structure
- Client configuration (s2c_uae_test)
- BSR API specifications
- Testing fixtures
- **Status:** ✅ Complete, environment-specific

---

## 2. Pre-Build Actions (Your Checklist)

### 2.1 Environment Setup

**CRITICAL - Do This First:**

```bash
# 1. Add DATABASE_URL_DIRECT to .env
# Go to Supabase → Settings → Database → Connection string → Direct connection
# Add to .env file:
DATABASE_URL_DIRECT=postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

**Verify all variables:**
```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('DATABASE_URL:', '✓' if os.getenv('DATABASE_URL') else '✗')
print('DATABASE_URL_DIRECT:', '✓' if os.getenv('DATABASE_URL_DIRECT') else '✗')
print('LWA_CLIENT_ID:', '✓' if os.getenv('LWA_CLIENT_ID') else '✗')
print('LWA_CLIENT_SECRET:', '✓' if os.getenv('LWA_CLIENT_SECRET') else '✗')
print('AWS_ACCESS_KEY_ID:', '✓' if os.getenv('AWS_ACCESS_KEY_ID') else '✗')
"
```

**Expected output:** All ✓

---

### 2.2 Create Feature Branch

```bash
cd ~/path/to/saddl
git checkout -b feature/diagnostic-tool
git push -u origin feature/diagnostic-tool
```

---

### 2.3 Capture Baseline

**Database schema baseline:**
```bash
python3 << 'EOF'
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

cur.execute("""
    SELECT table_schema, table_name, 
           (SELECT COUNT(*) FROM information_schema.columns c 
            WHERE c.table_schema = t.table_schema 
            AND c.table_name = t.table_name) as column_count
    FROM information_schema.tables t
    WHERE table_schema IN ('public', 'sc_raw', 'sc_analytics')
    ORDER BY table_schema, table_name
""")

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'baseline_schema_{timestamp}.txt'

with open(filename, 'w') as f:
    f.write("SADDL Schema Baseline - Pre-Diagnostic Tool\n")
    f.write(f"Captured: {datetime.now()}\n\n")
    
    current_schema = None
    for schema, table, col_count in cur.fetchall():
        if schema != current_schema:
            f.write(f"\n{schema} schema:\n")
            f.write("-" * 50 + "\n")
            current_schema = schema
        f.write(f"  {table} ({col_count} columns)\n")

conn.close()
print(f"✅ Baseline saved to: {filename}")
EOF
```

---

### 2.4 Backup Database

**Option 1 - Supabase Dashboard:**
- Go to Supabase Dashboard → Database → Backups
- Create manual backup with label "pre-diagnostic-tool"

**Option 2 - Manual pg_dump (if you have psql installed):**
```bash
# Install if needed: brew install libpq
# Then: echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc

pg_dump $DATABASE_URL_DIRECT > backup_pre_diagnostic_$(date +%Y%m%d).sql
```

---

### 2.5 Test Existing System

**Verify nothing is broken before starting:**

```bash
# Run existing app
streamlit run ppcsuite_v4_ui_experiment.py

# Test in browser:
# 1. Navigate to Impact Dashboard
# 2. Verify data loads
# 3. Navigate to Campaigns
# 4. Verify data loads
# 5. Navigate to Targets
# 6. Verify data loads

# All pages should work normally
```

---

## 3. Claude Code Handoff Package

### 3.1 What to Give Claude Code

**Provide all 5 documents in this order:**

1. **SADDL_Diagnostics_PRD_v2.md** - "What to build"
2. **SADDL_Backend_Architecture.md** - "Database design"
3. **SADDL_Frontend_Architecture.md** - "UI/UX design"
4. **SADDL_Implementation_Guardrails.md** - "Safety rules"
5. **SADDL_Context_Variables.md** - "Your environment specifics"

**Opening prompt for Claude Code:**

```
I need you to build the SADDL Diagnostic Intelligence Layer exactly as 
specified in these 5 documents. 

CRITICAL RULES:
1. You MUST read all 5 documents before starting
2. You MUST write tests BEFORE implementation
3. You MUST stop at each validation gate and report status
4. You MUST NOT modify public schema or existing files
5. You MUST follow the phased approach (Phase 1 → Gate → Phase 2 → Gate → Phase 3)

CONFIRM YOU HAVE READ AND UNDERSTOOD:
- All database write boundaries
- The schema isolation requirements
- The three validation gates
- The rollback procedures

Once you confirm, we'll start with Phase 1: BSR Pipeline.
```

---

### 3.2 Expected Claude Code Response

Claude Code should respond with:

```
✅ I have read all 5 documents:
   1. PRD v2 - Diagnostic tool feature spec
   2. Backend Architecture - PostgreSQL schema design
   3. Frontend Architecture - Glassmorphic UI design
   4. Implementation Guardrails - Safety rules and tests
   5. Context Variables - Environment-specific config

✅ I understand the following boundaries:
   - NEVER write to public schema
   - NEVER modify existing files (only create new ones)
   - NEVER modify actions_log table
   - ONLY write to sc_raw and sc_analytics schemas

✅ I will follow the phased approach:
   - Phase 1: BSR pipeline + tests
   - Validation Gate 1: Test passage required
   - Phase 2: Signal detection + tests
   - Validation Gate 2: Test passage required
   - Phase 3: UI pages + tests
   - Validation Gate 3: Final acceptance

✅ I will write tests before implementation

Ready to begin Phase 1: BSR Pipeline implementation.
Shall I proceed?
```

**If Claude Code does NOT confirm all of the above, do NOT proceed.**

---

## 4. Phase Execution Plan

### Phase 1: BSR Pipeline (Week 1-2)

**Claude Code Tasks:**
1. Create `pipeline/bsr_pipeline.py`
2. Create `sc_raw.bsr_history` table migration
3. Create `sc_analytics.bsr_trends` view
4. Write 5 BSR pipeline tests
5. Run 90-day backfill

**Your Tasks:**
1. Monitor backfill progress
2. Review test results
3. Verify BSR data populated

**Validation Gate 1:**
```bash
# All tests must pass
pytest tests/test_schema_isolation.py
pytest tests/test_bsr_pipeline.py

# BSR data must be present
python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT COUNT(*), COUNT(DISTINCT asin) FROM sc_raw.bsr_history')
print(f'Rows: {cur.fetchone()}')
conn.close()
"
# Expected: ~10,000-15,000 rows, ~100 ASINs

# ✅ PASS → Proceed to Phase 2
# ❌ FAIL → Fix issues, re-run gate
```

---

### Phase 2: Signal Detection (Week 3-4)

**Claude Code Tasks:**
1. Create 5 signal detection views
2. Create signal detection functions in `utils/diagnostics.py`
3. Create Impact Dashboard integration in `utils/diagnostics.py`
4. Write 8 signal detection tests
5. Write 3 integration tests

**Your Tasks:**
1. Review SQL queries for accuracy
2. Test signal detection with real data
3. Verify Impact Dashboard integration works

**Validation Gate 2:**
```bash
# All tests must pass
pytest tests/test_signal_detection.py
pytest tests/test_integration.py

# All signal views must work
for signal in demand_contraction organic_decay non_advertised_winners harvest_cannibalization over_negation
do
  python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(f'SELECT COUNT(*) FROM sc_analytics.signal_{signal}')
print(f'{signal}: {cur.fetchone()[0]} rows')
conn.close()
  "
done

# Impact Dashboard integration works
python3 -c "
from utils.diagnostics import get_recent_validation_summary
summary = get_recent_validation_summary('s2c_uae_test', days=7)
print(f'Total actions: {summary[\"total_actions\"]}')
print(f'Win rate: {summary[\"win_rate\"]}%')
"

# ✅ PASS → Proceed to Phase 3
# ❌ FAIL → Fix issues, re-run gate
```

---

### Phase 3: UI & Visualization (Week 5-6)

**Claude Code Tasks:**
1. Create `features/diagnostics/` module
2. Create 3 Streamlit pages (overview, signals, trends)
3. Create glassmorphic components
4. Create SVG icon library
5. Write 5 performance tests
6. Create CSS injection

**Your Tasks:**
1. Review UI in browser
2. Test on mobile/tablet
3. Cross-browser testing (Chrome, Safari, Firefox)
4. Verify cross-links to Impact Dashboard work

**Validation Gate 3:**
```bash
# All tests pass
pytest tests/test_performance.py

# UI renders without errors
streamlit run features/diagnostics/main.py &
# Visit http://localhost:8501
# Navigate through all 3 pages
# Verify no console errors
# Verify charts render
# Click cross-links to Impact Dashboard

# Existing pages still work
# Visit Campaigns, Targets, Impact Dashboard
# Verify nothing broke

# ✅ PASS → Ready for production
# ❌ FAIL → Fix issues, re-run gate
```

---

## 5. Success Criteria

### 5.1 Technical Acceptance

**All of these must be true:**

```
✅ All 26+ tests passing
✅ Schema isolation tests passing (no public schema writes)
✅ BSR data populated (10k+ rows, 100+ ASINs)
✅ All 5 signal views returning data
✅ Impact Dashboard integration working (read-only)
✅ All 3 diagnostic pages rendering
✅ No modifications to existing files
✅ No modifications to public schema
✅ Glassmorphic design system applied
✅ SVG icons used (no bitmap emojis)
✅ Responsive design working
✅ Performance tests passing (queries <2s, page loads <5s)
```

### 5.2 Functional Acceptance

**Manual verification:**

```
□ Demand contraction signal detects market-wide CVR decline
□ Organic decay signal detects ASINs losing BSR rank
□ Non-advertised winners identifies high-performing organic ASINs
□ Harvest cannibalization detects efficiency without growth
□ Over-negation detects volume cuts
□ Overview page shows account health summary
□ Signals page shows all active alerts
□ Trends page shows charts and correlation matrix
□ Cross-links to Impact Dashboard work
□ Recent optimization context displays correctly
□ Mobile layout works on phone
□ All charts render correctly
□ No console errors
```

### 5.3 Safety Verification

**Final safety check:**

```bash
# Verify public schema unchanged
python3 << 'EOF'
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Get current table count in public schema
cur.execute("""
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_schema = 'public'
""")
current_count = cur.fetchone()[0]

# Compare to baseline (from your baseline_schema_*.txt file)
baseline_count = 18  # Update this from your baseline file

if current_count == baseline_count:
    print(f"✅ Public schema unchanged ({current_count} tables)")
else:
    print(f"⚠️  WARNING: Public schema changed!")
    print(f"   Baseline: {baseline_count} tables")
    print(f"   Current: {current_count} tables")
    
conn.close()
EOF
```

---

## 6. Rollback Plan

### 6.1 If Something Goes Wrong

**Database rollback:**
```bash
# Drop diagnostic schemas
python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL_DIRECT'])
cur = conn.cursor()
cur.execute('DROP SCHEMA IF EXISTS sc_raw CASCADE')
cur.execute('DROP SCHEMA IF EXISTS sc_analytics CASCADE')
conn.commit()
print('✅ Diagnostic schemas dropped')
conn.close()
"
```

**Code rollback:**
```bash
# Revert to main branch
git checkout main
git branch -D feature/diagnostic-tool
```

**Verify existing system still works:**
```bash
streamlit run ppcsuite_v4_ui_experiment.py
# Test all existing pages
```

---

### 6.2 If Supabase Needs Full Restore

**From Supabase dashboard backup:**
1. Go to Supabase → Database → Backups
2. Find "pre-diagnostic-tool" backup
3. Click Restore

**From manual pg_dump backup:**
```bash
# Restore from file
psql $DATABASE_URL_DIRECT < backup_pre_diagnostic_20260218.sql
```

---

## 7. Post-Deployment

### 7.1 Monitoring

**First 24 hours:**
- Monitor query performance (should be <2s)
- Monitor page load times (should be <5s)
- Check for errors in logs
- Verify BSR pipeline runs successfully overnight

**First week:**
- Verify signals are detecting correctly
- Check false positive rate (<15%)
- Monitor user engagement (visits per week)
- Gather user feedback

---

### 7.2 Optimization Opportunities

**After 1 week of stable operation:**
- Consider materializing slow signal views
- Add additional indexes if queries slow
- Cache frequently accessed signals
- Add more ASINs to BSR tracking if needed

---

## 8. Final Checklist

**Before giving to Claude Code:**

```
Environment Setup:
□ DATABASE_URL_DIRECT added to .env
□ All environment variables verified
□ Feature branch created
□ Baseline schema captured
□ Database backup taken
□ Existing system tested and working

Documentation:
□ All 5 documents reviewed
□ PRD v2 understood
□ Backend architecture understood
□ Frontend architecture understood
□ Guardrails understood
□ Context variables understood

Handoff Preparation:
□ Opening prompt prepared
□ Validation gates understood
□ Rollback procedures understood
□ Success criteria defined
□ Monitoring plan ready

Claude Code Readiness:
□ Confirmation that Claude Code read all 5 docs
□ Confirmation of boundary understanding
□ Confirmation of phased approach
□ Confirmation of test-first methodology
```

**When all checkboxes are ✅ → START PHASE 1**

---

## 9. Estimated Timeline

**Conservative estimate with gates:**

| Phase | Duration | Tasks |
|---|---|---|
| Phase 1: BSR Pipeline | 1-2 weeks | Pipeline + tests + backfill |
| Gate 1 | 1 day | Validation and approval |
| Phase 2: Signal Detection | 1-2 weeks | Views + tests + integration |
| Gate 2 | 1 day | Validation and approval |
| Phase 3: UI | 1-2 weeks | Pages + components + design |
| Gate 3 | 1 day | Final validation |
| **Total** | **5-7 weeks** | **Includes contingency** |

**Aggressive estimate (if everything works first time):**

| Phase | Duration |
|---|---|
| Phase 1 | 1 week |
| Phase 2 | 1.5 weeks |
| Phase 3 | 1.5 weeks |
| **Total** | **4 weeks** |

---

## 10. Contact Points

**If Claude Code gets stuck:**

1. **Schema issues:** Refer to Backend Architecture doc
2. **UI/design questions:** Refer to Frontend Architecture doc
3. **Safety concerns:** STOP and re-read Guardrails doc
4. **Environment errors:** Check Context Variables doc
5. **Feature questions:** Refer to PRD v2

**Escalation:**
- If Claude Code violates any guardrail → STOP immediately
- If tests don't pass → Don't proceed to next phase
- If unclear about requirement → Ask before implementing

---

**🚀 You are now ready to hand this to Claude Code.**

**The package is comprehensive, safe, and production-ready.**

---

*Handoff Checklist v1.0 - Complete implementation guide*
