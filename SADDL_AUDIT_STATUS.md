# SADDL AdPulse — Audit & Fix Status
> Last updated: 2026-03-11 | Total issues audited: 138 | Fixed: 44 | Remaining: ~94

Use this file as context for every Claude Code session. Paste it at the top with: "Here is the current audit status for this codebase."

---

## WHAT HAS BEEN DONE

### Round 1 — Wrong Data (Wave 1 + Wave 2)
**Branch:** `fix/audit-track1-track2` → merged to `main`
**Commits:** `0a040e2` (Wave 1), `91e6807` (Wave 2), plus DB error gap patch on `features/impact/main.py`

| Fix ID | File | What Was Fixed |
|--------|------|----------------|
| FIX-1 | app_core/seeding.py | Hardcoded admin123 replaced with env-var bootstrap + RuntimeError guard |
| FIX-2 | worker.py | Global os.environ token mutation removed; refresh_token passed explicitly |
| FIX-3 | worker.py | Infinite backfill loop on new accounts with 0 sales history fixed |
| FIX-4 | features/platform_admin.py | has_permission() + st.stop() gate added as first line of entry |
| FIX-5 | app_core/auth/service.py | Welcome123! replaced with secrets.token_urlsafe(16) per invite |
| FIX-6 | features/impact_metrics.py | decision_impact filtered to exclude Market Drag rows; raw preserved for debug |
| FIX-7 | features/impact/components/hero.py | Hero % denominator fixed to total_after_sales only (was summing both periods) |
| FIX-8 | features/impact_metrics.py + analytics.py | spend_filtered_impact moved into ImpactMetrics; single source of truth |
| FIX-9 | features/impact/components/roas_waterfall.py | effective_spend floor = max(after_spend, 10.0) to prevent micro-spend inflation |
| FIX-10 | utils/metrics.py + dashboard/metrics.py + business_overview.py | ACoS 100x format mismatch fixed; calculate_tacos() returns *100; 7 call sites patched |
| FIX-11 | app_core/roas_waterfall_v33.py | Fake $0.50 CPC hardcode removed; clicks_available=False; CVR/SPC return None |
| FIX-12 | features/impact/data/fetchers.py + impact/main.py | DB error returns {'status':'error'}; main.py shows st.error + st.stop() |
| FIX-13 | features/impact/components/tables.py | is_mature gate added as first line of get_decision_outcome() |
| FIX-14 | app_core/roas_waterfall_v33.py | np.clip(market_shift, 0.5, 1.5) removed; warning log fires outside range |
| FIX-15 | app_core/data_hub.py + ui/data_hub.py | DB save failure returns (False, error); persistent warning banner added |
| PATCH | features/impact/main.py | get_available_dates() and get_latest_raw_data_date() wrapped with try/except |

---

### Round 2 — Security (Wave 1 + Wave 2)
**Branch:** `fix/security-audit` → merged to `main`
**Commits:** `df11b99` (Wave 1), `1834c20` (Wave 2), plus PERMISSION_MATRIX patch

| Fix ID | File | What Was Fixed |
|--------|------|----------------|
| SEC-1 | supabase/functions/amazon-oauth-callback/index.ts | OAuth callback now verifies state param exists in client_settings before writing token; returns 400 for unknown state |
| SEC-2 | features/dashboard/data_access.py | f-string SQL interpolation replaced with %s parameterized queries throughout |
| SEC-3 | features/debug_ui.py | Production env guard (SADDL_ENV=production) + client_id validated against user_accounts |
| SEC-4 | ui/data_hub.py | Three validation gates: same-account check, source row count, post-UPDATE affected row count |
| SEC-5 | app_core/auth/service.py | sign_in(email, password, org_id=None) — org checked after query |
| SEC-6 | app_core/auth/service.py | secrets.token_urlsafe(32) session token generated on login; validate_session() added; token cleared on sign-out |
| SEC-7 | app_core/auth/service.py | os.urandom(4).hex()+'!' replaced with secrets.token_urlsafe(12)+'Aa1!' — satisfies complexity rules |
| SEC-8 | app_core/auth/invitation_service.py | Invitation tokens hashed with bcrypt before DB insert; verify_password() on validation; raw token still sent to email |
| SEC-9 | app_core/platform_service.py | uuid.uuid4() fallback for invited_by_user_id removed; ValueError raised if no creator ID |
| SEC-10 | app_core/auth/middleware.py | Decorator three-level nesting confirmed correct; logic bug comment removed; docstring added |
| PATCH | app_core/auth/middleware.py | 'platform_admin': [Role.OWNER] added to PERMISSION_MATRIX (was missing, blocked all users) |

---

### Round 3 — GHOST-4: Live Dependency in Wrong Location
**Commit:** `57e2fbe`

| Fix ID | Files Changed | What Was Fixed |
|--------|--------------|----------------|
| GHOST-4a | app_core/optimization_types.py | Created canonical home for all optimizer types: `OptimizationRecommendation`, `RecommendationValidator`, `validate_recommendation`, `validate_recommendations_batch`, `validate_campaign_name_chars`, `get_currency_limits`, `CURRENCY_LIMITS` |
| GHOST-4b | features/optimizer_shared/__init__.py | Import updated from `dev_resources.tests.bulk_validation_spec` → `app_core.optimization_types` |
| GHOST-4c | features/optimizer_shared/strategies/negatives.py | Import updated; `OptimizationRecommendation`, `RecommendationType`, `validate_recommendation` now from `app_core.optimization_types` |
| GHOST-4d | features/optimizer_shared/strategies/bids.py | Import updated; `OptimizationRecommendation`, `RecommendationType`, `validate_recommendation` now from `app_core.optimization_types` |

**Verified:** `grep -rn "from dev_resources" . --include="*.py"` → 0 matches. All `OptimizationRecommendation` references point to `app_core.optimization_types`.

---

### Round 4 — Constants, Format Locks, CVR Unification
**Commit:** *(this session)*

#### MAGIC-4 — Centralize ACTION_MATURITY_DAYS (12 instances → 1 constant)
| Fix ID | File | What Was Fixed |
|--------|------|----------------|
| MAGIC-4a | app_core/constants.py | Created; `ACTION_MATURITY_DAYS = 14` defined as project-wide constant |
| MAGIC-4b | app_core/timeline_roas.py | 4 hardcoded `14` / `timedelta(days=14)` replaced with `ACTION_MATURITY_DAYS` |
| MAGIC-4c | app_core/utils.py | `"before_window_days": 14`, `"days": 14`, `"maturity": 17` replaced |
| MAGIC-4d | ui/layout.py | `timedelta(days=14)` pending_count cutoff replaced |
| MAGIC-4e | features/debug_ui.py | `< 14` and `>= 14` maturity checks replaced |
| MAGIC-4f | scripts/check_cooldown.py | SQL `< 14` and print strings replaced |
| MAGIC-4g | scripts/ml_bid_optimizer.py | `timedelta(days=14)` pre/post windows replaced |
| MAGIC-4h | scripts/ml_bid_optimizer_30d.py | `timedelta(days=14)` pre window replaced |

#### DUPLICATE-3 — Lock TACoS/ACoS format to percentage (0-100)
| Fix ID | File | What Was Fixed |
|--------|------|----------------|
| DUP3a | ui/performance_dashboard/ppc_overview.py | `_build_stats`: acos and p_acos now `* 100`; `_build_campaign_df`: camp["acos"] now `* 100`; display calls updated to `_fmt_pct_already` |
| DUP3b | scripts/ml_bid_optimizer.py | `aggregate_metrics`: `'acos': spend / sales` → `spend / sales * 100` |
| DUP3c | scripts/ml_bid_optimizer_30d.py | Same fix as DUP3b |
| DUP3d | app_core/constants.py | `TACOS_FORMAT = "percentage"` added as project-wide convention |

#### DUPLICATE-5 — Counterfactual model audit
| Fix ID | File | Finding |
|--------|------|---------|
| DUP5 | app_core/roas_attribution.py + app_core/timeline_roas.py | **No changes — not interchangeable.** `roas_attribution` = market-forces waterfall (CPC/CVR/AOV decomposition). `timeline_roas` = before/after anchor ROAS. `roas_attribution` usage already commented out in `features/impact/main.py` with a noted mathematical flaw. No unification applicable. |

#### DUPLICATE-6 — Canonical CVR function
| Fix ID | File | What Was Fixed |
|--------|------|----------------|
| DUP6a | utils/metrics.py | `calculate_cvr(orders, clicks)` added as canonical ad-CVR function (returns ratio 0-1, None on zero clicks) |
| DUP6b | app_core/roas_attribution.py | Inline `orders / clicks if clicks > 0 else 0` replaced with `calculate_cvr(orders, clicks) or 0` |

**⚠️ Known naming collision (follow-up needed):** Two functions named `calculate_cvr` exist — `utils/metrics.py` (ad clicks-based) and `features/dashboard/metrics.py` (website sessions-based). Not a bug, but rename to `calculate_ad_cvr` / `calculate_session_cvr` in next sprint.

---

## WHAT IS STILL PENDING

### DUPLICATES — Remaining
| ID | Metric | Conflict | Risk |
|----|--------|----------|------|
| DUPLICATE-CVR-NAME | calculate_cvr naming collision | `utils/metrics.py` (ad clicks-based) vs `features/dashboard/metrics.py` (website sessions-based) share same function name | Rename to `calculate_ad_cvr` / `calculate_session_cvr` to prevent silent import confusion |

---

### PERFORMANCE — Not blocking but will become painful
| ID | File | Issue | Impact |
|----|------|-------|--------|
| A-39 | features/optimizer/bids.py | apply() runs row-wise on 50k targets — 30s+ optimization runs | Vectorize with np.where or pd.eval |
| SESSION-4 | features/dashboard/business_overview.py | No @st.cache_data — full DB query on every rerender | Add @st.cache_data(ttl=300) to all heavy queries |

---

### ORPHAN FILES — Safe to delete
| File | Why Safe |
|------|----------|
| features/optimizer_ui.py | Superseded by optimizer_v2 |
| features/diagnostics/*_old.py (3 files) | Superseded by control_center.py |
| ui/components/legacy.py | Superseded |

---

### ORPHAN FILES — Review before deleting
| File | Why Caution |
|------|-------------|
| scripts/reaggregate_s2c_test.py | Direct DB mutation + hardcoded credentials — verify no active use before deleting |
| scripts/create_s2c_admin.py | Credential-seeding script — verify replaced by seeding.py bootstrap before deleting |

---

### REMAINING CLUSTER ISSUES (from original 138-issue audit)
These are the ~88 MEDIUM/LOW issues not yet addressed. They are not day-1 customer trust-breakers but are real debt.

| Cluster | Count | Top Risk |
|---------|-------|----------|
| A — PPC Engine | ~26 medium, 3 low | Vectorize bids.py apply() (A-39) |
| B — Impact Layer | ~3 medium | ~~Dual counterfactual models~~ ✅ audited — `roas_attribution` disabled; remaining: waterfall chart accuracy |
| C — API Integrations | ~11 medium | SP-API pagination not handling 429 rate limits gracefully |
| D — Data Pipeline | ~12 medium, 1 low | aggregator.py missing idempotency check on re-runs |
| E — Auth/UI/Routing | ~3 medium, 1 low | Session state shortcuts causing 10s+ Business Overview loads |

---

## RECOMMENDED NEXT SPRINT ORDER

1. ~~**GHOST-4a–4d**~~ ✅ Done (4 fixes) — `57e2fbe`
2. ~~**MAGIC-4a–4h**~~ ✅ Done (8 fixes) — this session
3. ~~**DUPLICATE-3a–3d**~~ ✅ Done (4 fixes) — this session
4. ~~**DUPLICATE-5**~~ ✅ Audited — no unification needed; `roas_attribution` already disabled in `impact/main.py`
5. ~~**DUPLICATE-6a–6b**~~ ✅ Done (2 fixes) — this session
6. **DUPLICATE-CVR-NAME** — Rename `calculate_cvr` collision. 30 min. Prevents silent wrong-function imports.
7. **SESSION-4 + A-39** — Performance. 1 session. Needed before scale.
8. **Orphan cleanup** — Delete safe files, review flagged scripts. 30 min.

---

## HOW TO USE THIS FILE

Paste at the top of any Claude Code session:
```
Here is the current audit and fix status for the Saddl AdPulse codebase.
Use this as context before reading any files or making any changes.
[paste file contents]
```

Update the DONE sections after each sprint by moving items from PENDING → DONE with the commit hash.
