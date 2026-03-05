# SADDLE ADPULSE
## Comprehensive Code Audit & Test Plan
### Version 2.0 | January 29, 2026
#### Prepared for Production Readiness Assessment

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Desktop Application Audit](#3-desktop-application-audit)
4. [Landing Site Audit](#4-landing-site-audit)
5. [Mobile App Assessment](#5-mobile-app-assessment)
6. [Codebase Hygiene & Dead Code](#6-codebase-hygiene--dead-code)
7. [Security Review](#7-security-review)
8. [Prioritized Remediation Plan](#8-prioritized-remediation-plan)
9. [Appendix: File Health Matrix](#9-appendix-file-health-matrix)

---

## 1. Executive Summary

### What Changed Since V1.0 (Jan 22, 2026)

Since the initial audit, significant features have been added: auth/invitation system, impact dashboard, executive dashboard, mobile companion app, Remotion video generation, pricing/terms pages, and PostgreSQL migration. However, the rapid iteration has accumulated substantial tech debt:

| Metric | V1.0 (Jan 22) | V2.0 (Jan 29) | Delta |
|--------|---------------|----------------|-------|
| Python LOC (desktop) | ~22,000 | ~30,000+ | +36% |
| HTML pages (landing) | 15 | 21 | +40% |
| CSS total (landing) | ~40KB | ~60KB | +50% |
| Dead/commented code | ~5% | ~15-20% | +3x |
| Archived directories | 1 | 3 (10.2MB) | +9x |
| Platforms | 2 | 4 (desktop, landing, mobile, video) | +2x |

### Top 5 Issues

1. **Dashboard duplication** - `impact_dashboard.py` (4,083 LOC) and `executive_dashboard.py` (1,926 LOC) share ~40% identical logic
2. **10.2MB of archived dead code** sitting in the repo across 3 archive directories
3. **Landing site: 100% copy-paste** for nav/footer across 21 HTML files (no templating)
4. **31% of script.js is commented-out** dead code from disabled features
5. **44% of styles.css is unused** (about page, modals, quiz styles loaded globally)

### Severity Distribution

```
CRITICAL  ████░░░░░░  4 issues   (blocking / high waste)
HIGH      ██████░░░░  8 issues   (should fix soon)
MEDIUM    ████████░░ 12 issues   (fix when able)
LOW       ██████████  6 issues   (nice to have)
```

---

## 2. Architecture Overview

### Current Platform Map

```
saddle/
├── desktop/          Python/Streamlit    30,000+ LOC   PRODUCTION
│   ├── core/         DB, auth, data      10,172 LOC
│   ├── features/     Business logic      19,767 LOC
│   ├── ui/           Layouts, themes     ~3,000 LOC
│   ├── utils/        Helpers             ~500 LOC
│   ├── api/          External APIs       ~400 LOC
│   └── config/       Settings            ~300 LOC
│
├── landing/          HTML/CSS/JS         21 pages       PRODUCTION
│   ├── styles.css    Main stylesheet     1,926 lines
│   ├── script.js     Core JS             537 lines
│   ├── audit.js      Quiz tool           320 lines
│   └── 4 page CSS    Page-specific       ~1,300 lines
│
├── mobile/           React Native/Expo   34 TS files    DEVELOPMENT
│   └── src/          Screens, components, navigation
│
└── remotion-video/   React/Remotion      16 scenes      COMPLETE
    └── src/          Video compositions
```

### Largest Modules (Risk Surface)

| Module | LOC | Responsibility | Risk |
|--------|-----|----------------|------|
| `impact_dashboard.py` | 4,083 | Impact analysis, waterfall, confidence scoring | HIGH - too many responsibilities |
| `postgres_manager.py` | 2,833 | PostgreSQL orchestration | MEDIUM - critical but focused |
| `optimizer.py` | 2,662 | Bid optimization engine | LOW - well-scoped |
| `assistant.py` | 2,246 | AI insights (Anthropic API) | LOW - isolated |
| `executive_dashboard.py` | 1,926 | Executive view (overlaps impact_dashboard) | HIGH - redundant |
| `db_manager.py` | 1,878 | DB abstraction layer | MEDIUM - dual-mode complexity |
| `report_card.py` | 1,817 | Account health scoring | LOW - focused |
| `styles.css` (landing) | 1,926 lines | Global styles | HIGH - 44% unused |

---

## 3. Desktop Application Audit

### 3.1 CRITICAL: Dashboard Module Duplication

**Files**: `features/impact_dashboard.py` + `features/executive_dashboard.py`

Both modules independently calculate:
- Revenue timelines with decision markers
- KPI cards and metrics
- ROAS/CVR/CPC calculations (identical formulas)
- Impact attribution logic

`executive_dashboard.py` imports from `impact_dashboard.py` but then re-implements similar logic, creating circular dependency risk (noted in comments about preventing circular imports).

**Shared calculation pattern appearing in both files:**
```python
df['ROAS'] = (df['Sales'] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
df['CVR'] = (df['Orders'] / df['Clicks'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
df['CPC'] = (df['Spend'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
```

This pattern also appears in `report_card.py` and `data_hub.py`.

**Recommendation**: Extract shared metric calculations into `utils/calculations.py`. Merge dashboard modules into a single module with view-mode parameter.

---

### 3.2 HIGH: layout.py Code Quality Issues

**File**: `desktop/ui/layout.py`

| Line(s) | Issue | Severity |
|---------|-------|----------|
| 49-50 | `navigate_to()` called twice consecutively (duplicate call) | HIGH |
| 625-677 | Entire ROAS calculation + `calc_efficiency()` defined twice; first block is dead code | CRITICAL |
| 170-302 | 130 lines of CSS embedded in Python strings | MEDIUM |
| 689-694 | Comment says "silently handle" but displays error; redundant `import st` and `pass` | LOW |
| 122-123 | Duplicate comment headers | LOW |

---

### 3.3 HIGH: report_card.py Contradictory Logic

**File**: `features/report_card.py`

Lines 137-142 contain a calculation that overwrites itself:
```python
actual_roas = total_spend / total_sales if total_sales > 0 else 0  # ACOS (wrong)
# Comments noting confusion about ROAS vs ACOS...
actual_roas = total_sales / total_spend if total_spend > 0 else 0  # ROAS (correct)
```

Line 137 is dead code - it computes ACOS but is immediately overwritten by the correct ROAS formula on line 142. The confused comments suggest this was debugged live and never cleaned up.

Additional: Line 70 uses lowercase `tuple` type hint (`-> tuple[bool, str]`) which breaks Python <3.10 compatibility, despite `Tuple` being imported from `typing`.

---

### 3.4 MEDIUM: data_hub.py Incomplete Validation

**File**: `core/data_hub.py`

Lines 341-347 contain a validation check that does nothing:
```python
if not all(col in df_renamed.columns for col in required_cols):
    # Fallback: Try to be lenient
    pass  # NO ACTUAL LOGIC
```

This creates silent data quality issues. Either implement the fallback logic or raise an explicit error.

Additional issues:
- Session state initialization pattern (`upload_timestamps`) repeated 3+ times - should be a helper
- Commented-out toast notification on line 280 left in production code
- Inconsistent indentation in multiple locations

---

### 3.5 MEDIUM: ppcsuite_v4_ui_experiment.py Status

**File**: `desktop/ppcsuite_v4_ui_experiment.py` (79KB)

This file appears to be a deprecated entry point. Issues:
- Triple-duplicate comment blocks for section headers
- `dotenv` soft-imported but used without checking import success
- Catches `FileNotFoundError` for `st.secrets` (wrong exception type - should be `KeyError`)
- Comments about "delayed imports" immediately followed by eager imports (defeats purpose)

**Question**: Is this file still the active entry point, or has it been superseded? If deprecated, it should be archived.

---

### 3.6 MEDIUM: impact_dashboard.py Complexity

**File**: `features/impact_dashboard.py` (4,083 LOC)

The `_ensure_impact_columns()` function performs 11 distinct operations in a single function. Should be decomposed into:
- `_calculate_metrics()` - SPC, CPC, expected clicks/sales
- `_apply_guards()` - low-sample mask, confidence thresholds
- `_classify_market_tags()` - market condition assignment

Match type inference logic (`infer_mt()`) is duplicated between this file and `data_hub.py`.

---

### 3.7 LOW: theme.py Caching Inefficiency

**File**: `desktop/ui/theme.py`

`get_cached_logo()` uses `@st.cache_data(ttl=3600)` but theme changes call `st.rerun()` which invalidates all caches, making the TTL pointless. The 278 lines of nested CSS rules contain redundant selectors and hardcoded color values that bypass the CSS variables already defined.

---

## 4. Landing Site Audit

### 4.1 CRITICAL: Navigation/Footer Duplication

Every HTML page contains identical copies of:
- **Navigation**: ~22 lines, 8+ copies = 176+ redundant lines
- **Footer**: ~46 lines, 8+ copies = 368+ redundant lines
- **Head section**: Font preconnects, meta tags, inline styles

Changing a nav link requires editing 8+ files. This is the single biggest maintenance risk.

**Note**: `features.html` is missing the JetBrains Mono font declaration present on other pages.

---

### 4.2 CRITICAL: styles.css (1,926 lines) - 44% Waste

| Lines | Issue | Size |
|-------|-------|------|
| 67-76 | `.navbar` defined, then overridden by duplicate at lines 160-169 (different background color) | Dead: 10 lines |
| 117-138 vs 197-213 | `.primary-button-large` defined twice with different box-shadows | Dead: 17 lines |
| 852-1150 | About page styles in global stylesheet | 299 lines (unused on other pages) |
| 1152-1707 | Quiz/audit modal + beta signup styles in global stylesheet | 555 lines (unused on most pages) |
| 313-386 | Unused color utility classes (`.highlight-green`, `.icon-green/blue/purple/dark`, `.feature-card-dark`) | ~70 lines |

**CSS Variable Duplication** - Same color (`#0F172A`) mapped to 4 variable names:
```
--color-slate-900, --color-wine, --color-dark, --color-text-primary
```

**Unused CSS variables**: `--shadow-sm`, `--color-wine-light`, `--color-dark-soft`, `--color-light-gray`

---

### 4.3 CRITICAL: script.js - 31% Dead Code

**File**: `landing/script.js` (537 lines)

| Lines | Description | Status |
|-------|-------------|--------|
| 5-59 | Persona state management (filtering, switching) | Commented out - "DISABLED FOR PRIVATE BETA" |
| 256-368 | Pricing toggle + ICP card interactions | Commented out - "DISABLED FOR PRIVATE BETA" |
| 97 | `lastScroll` variable assigned but never read | Dead variable |
| 223-226 | `.hero-stats` observer - element doesn't exist in HTML | Dead code |

**Performance Issues:**
- Scroll event handler (lines 82-98) fires 60+ times/sec with no throttling, sets inline styles instead of CSS classes
- Two separate ESC key listeners for two modals instead of one combined listener
- Intersection Observer sets animation via inline styles (should use CSS classes)
- Dynamic `<style>` tag injected via JS (lines 155-173) - belongs in CSS file

---

### 4.4 HIGH: Page-Specific CSS Overlap

| File | Lines | Overlap Issue |
|------|-------|---------------|
| `features-styles.css` | 316 | Line 72: `display: block !important` - unnecessary `!important` |
| `agencies-styles.css` | 377 | Lines 281-341: `.pricing-card` duplicates rules from `styles.css` |
| `compare-styles.css` | 346 | Lines 9-29: Heading styles could use global h1/h2 |

---

### 4.5 MEDIUM: audit.js Code Quality

**File**: `landing/audit.js` (320 lines)

- Inline `onclick` handlers in dynamically generated HTML (line 91) - should use `addEventListener`
- `JSON.stringify` inside template literal with hacky `.replace(/'/g, "&apos;")` - fragile
- Scoring multipliers `0.15` and `0.30` are magic numbers with no documentation
- Fallback factor strings duplicated (appear twice each in the file)
- Lines 298-319: File upload handler code references HTML elements that don't exist (dead code)

---

### 4.6 LOW: HTML Semantic Issues

- No `<main>` element on any page (affects accessibility/SEO)
- Pricing cards use `<div>` instead of `<article>`
- Missing `<meta>` description on some pages

---

## 5. Mobile App Assessment

**Directory**: `mobile/` (34 TypeScript files, React Native/Expo)

**Status**: Phase 6 (Polish) - Read-only companion app

**Architecture**: Clean separation (screens, components, services, theme, navigation). No major code quality issues detected. Well-structured with proper TypeScript types.

**Note**: Uses mock data (`mockData.ts`) - real API integration pending. Backend endpoint defined in `mobile_api.py`.

---

## 6. Codebase Hygiene & Dead Code

### 6.1 CRITICAL: Archive Directories (10.2MB in repo)

| Directory | Size | Contents |
|-----------|------|----------|
| `desktop/dev_resources/_archived_20260114_161409/` | 9.8MB | Old landing pages, migration scripts (25+), feature backups, Archive.zip |
| `desktop/dev_resources/_archived_cleanup_20260119/` | 80KB | Experimental backend, ingestion_v2 modules |
| `desktop/.backup_2024_12_18/` | 1.5MB | Manual point-in-time backup of 3 files |

**These should not be in the repo.** Git history preserves all prior states. Archives bloat clone times and confuse the active codebase.

### 6.2 HIGH: Deprecated Files

| File | Size | Status |
|------|------|--------|
| `ppcsuite_v4_ui_experiment.py` | 79KB | Labeled "experiment" - unclear if active |
| `desktop/dev_resources/frontend/` | ~2MB | Abandoned Next.js experiment - no integration |
| `landing/_archive/` | 56KB | Old beta pages + outdated documentation |
| `debug_sku_mapping.py` | ~5KB | One-off debugging utility |
| `verify_uuid.py` | ~2KB | One-off validation utility |
| 3x `migrate_orphaned_accounts*.py` | ~15KB | One-time migration scripts |

### 6.3 MEDIUM: dev_resources Bloat

`desktop/dev_resources/` contains:
- 40+ test files in `tests/` (many are one-off debugging scripts, not CI tests)
- 20+ analysis scripts in `scripts/` (one-time data explorations)
- 25+ completed migration scripts
- Redesign artifacts, agent outputs, design briefs

**Recommendation**: Keep `migrations/` and `documentation/`. Move everything else to a separate archive repo or delete.

---

## 7. Security Review

### 7.1 Input Validation

- **File uploads** (`data_hub.py` lines 287-289): No file type validation on upload - accepts any file extension
- **Session state**: Multiple locations access `st.session_state` without initialization guards
- **Hardcoded currency**: "AED" hardcoded in cache population (`data_hub.py` line 262) instead of pulling from account settings

### 7.2 Error Handling

- Silent `pass` statements in exception handlers (`data_hub.py` lines 347, 280) suppress errors without logging
- `ppcsuite_v4_ui_experiment.py` catches wrong exception types (`FileNotFoundError` instead of `KeyError`)

### 7.3 Secrets Management

- `.streamlit/secrets.toml` exists in the repo tree (should be `.gitignore`d)
- `python-dotenv` used for env management - ensure `.env` is gitignored

---

## 8. Prioritized Remediation Plan

### Phase 1: Immediate Cleanup (Day 1-2)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | Delete 3 archive directories (10.2MB) | Repo hygiene | 15 min |
| 2 | Remove or archive `ppcsuite_v4_ui_experiment.py` | Clarity | 15 min |
| 3 | Delete commented-out code in `script.js` (167 lines) | Clean JS | 15 min |
| 4 | Remove dead CSS rules in `styles.css` (duplicate `.navbar`, `.primary-button-large`) | Clean CSS | 30 min |
| 5 | Fix `report_card.py` dead ACOS line and type hint | Correctness | 15 min |
| 6 | Remove dead `layout.py` duplicate ROAS block (lines 625-650) and duplicate `navigate_to()` call | Correctness | 15 min |
| 7 | Delete `landing/_archive/` | Repo hygiene | 5 min |

### Phase 2: Code Quality (Day 3-5)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 8 | Extract shared metric calculations (`ROAS/CVR/CPC`) into `utils/calculations.py` | DRY | 2 hrs |
| 9 | Move about page CSS (299 lines) to `about-styles.css` | Performance | 1 hr |
| 10 | Move modal/quiz CSS (555 lines) to `modal-styles.css`, lazy-load | Performance | 1 hr |
| 11 | Consolidate CSS variables (4 names -> 1 per color) | Maintainability | 1 hr |
| 12 | Fix `data_hub.py` empty validation block (lines 341-347) | Correctness | 30 min |
| 13 | Add scroll throttling to `script.js` navbar handler | Performance | 30 min |
| 14 | Consolidate ESC key listeners in `script.js` | Clean code | 15 min |
| 15 | Add missing JetBrains Mono font to `features.html` | Consistency | 5 min |

### Phase 3: Architecture (Week 2)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 16 | Merge `executive_dashboard.py` into `impact_dashboard.py` with view modes | Major DRY | 4-6 hrs |
| 17 | Decompose `impact_dashboard.py` `_ensure_impact_columns()` into 3 functions | Maintainability | 2 hrs |
| 18 | Introduce HTML templating for landing nav/footer (Jinja2 or 11ty) | Major DRY | 4-6 hrs |
| 19 | Move inline CSS from `layout.py` (130 lines) to theme system | Clean code | 2 hrs |
| 20 | Replace `audit.js` inline onclick handlers with addEventListener | Clean code | 1 hr |
| 21 | Unify match type inference (single source in `utils/`) | DRY | 1 hr |

### Phase 4: Ongoing

| # | Action | Impact |
|---|--------|--------|
| 22 | Replace silent `pass` handlers with proper logging | Debuggability |
| 23 | Add file type validation to upload handlers | Security |
| 24 | Ensure `.env` and `secrets.toml` are in `.gitignore` | Security |
| 25 | Move dev_resources one-off scripts to archive repo | Hygiene |
| 26 | Add `<main>` semantic elements to all HTML pages | Accessibility |

---

## 9. Appendix: File Health Matrix

### Desktop Application

| File | LOC | Health | Key Issue |
|------|-----|--------|-----------|
| `features/impact_dashboard.py` | 4,083 | RED | Too many responsibilities, 11-op function |
| `features/executive_dashboard.py` | 1,926 | RED | ~40% overlap with impact_dashboard |
| `ui/layout.py` | ~800 | RED | Duplicate ROAS block, embedded CSS, duplicate nav call |
| `features/report_card.py` | 1,817 | YELLOW | Dead ACOS line, type hint issue |
| `core/data_hub.py` | 658 | YELLOW | Empty validation, repeated patterns |
| `ppcsuite_v4_ui_experiment.py` | ~2,000 | RED | Potentially deprecated, wrong exception types |
| `core/postgres_manager.py` | 2,833 | GREEN | Heavy but necessary |
| `features/optimizer.py` | 2,662 | GREEN | Well-scoped |
| `features/optimizer_ui.py` | 189 | GREEN | Clean, well-structured (model to follow) |
| `features/assistant.py` | 2,246 | GREEN | Isolated |
| `core/db_manager.py` | 1,878 | GREEN | Dual-mode complexity acceptable |
| `ui/theme.py` | ~300 | YELLOW | Cache inefficiency, redundant CSS selectors |

### Landing Site

| File | Lines | Health | Key Issue |
|------|-------|--------|-----------|
| `styles.css` | 1,926 | RED | 44% unused, duplicate rules, variable chaos |
| `script.js` | 537 | RED | 31% dead code, performance issues |
| `audit.js` | 320 | YELLOW | Magic numbers, inline handlers, dead upload code |
| `index.html` | 540 | YELLOW | Nav/footer duplication |
| All HTML (21 files) | ~8,000 | RED | No templating, full duplication |
| `features-styles.css` | 316 | YELLOW | Unnecessary !important |
| `agencies-styles.css` | 377 | YELLOW | Duplicate pricing-card rules |
| `how-styles.css` | 266 | GREEN | Minimal issues |
| `compare-styles.css` | 346 | GREEN | Minor heading overlap |

### Other Platforms

| Platform | Files | Health | Status |
|----------|-------|--------|--------|
| Mobile (`mobile/`) | 34 TS | GREEN | Clean architecture, proper types |
| Video (`remotion-video/`) | 16 TSX | GREEN | Complete, well-organized |
| Archives (3 dirs) | 10.2MB | RED | Should not be in repo |

---

*Audit conducted January 29, 2026*
*Version 2.0 - Comprehensive review of all main application files*
*Previous version: 1.0 (January 22, 2026)*
