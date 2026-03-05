**SADDLE ADPULSE**

Comprehensive Code Audit & Test Plan

Version 1.0

January 22, 2026

*Prepared for Production Readiness Assessment*

# 1. Executive Summary

This document presents a comprehensive test plan and code audit
framework for the Saddle AdPulse application, an Amazon PPC optimization
platform. The application has been iteratively developed over 2 months
and requires thorough verification before onboarding production users at
scale.

**Application Overview:** Python-based Streamlit application with
PostgreSQL backend, featuring PPC optimization, impact tracking, and
AI-powered analytics.

**Codebase Size:** \~48,000 lines of Python across 189 files

**Key Components:** Core data management (6,970 LOC), Features/Business
logic (19,013 LOC), UI layer (\~150 files)

**Current Test Coverage:** 31 test files in dev_resources/tests/

## 1.1 Audit Objectives

1.  Validate code structure follows software engineering best practices

2.  Identify and eliminate code redundancies and technical debt

3.  Ensure scalability for multi-user production workloads

4.  Verify data integrity and calculation accuracy

5.  Assess security posture for user authentication and data protection

6.  Establish comprehensive automated test coverage

# 2. Codebase Analysis Summary

## 2.1 Architecture Overview

The application follows a modular monolithic architecture with clear
separation between core services, features, and UI components.

  -----------------------------------------------------------------------
  **Layer**          **Location**               **Responsibility**
  ------------------ -------------------------- -------------------------
  Core               core/                      Data hub, DB management,
                                                authentication

  Features           features/                  Business logic,
                                                optimization engine

  UI                 ui/                        Streamlit components,
                                                layouts, themes

  API                api/                       External API clients
                                                (Anthropic, Rainforest)

  Config             config/                    Feature flags, design
                                                system

  Auth               auth/, core/auth/          Legacy + V2
                                                authentication
  -----------------------------------------------------------------------

## 2.2 Identified Areas of Concern

### 2.2.1 Large File Sizes (Refactoring Candidates)

  -----------------------------------------------------------------------
  **File**                              **Lines**       **Risk Level**
  ------------------------------------- --------------- -----------------
  features/impact_dashboard.py          4,082           HIGH

  features/optimizer.py                 2,662           MEDIUM

  core/postgres_manager.py              2,586           MEDIUM

  features/executive_dashboard.py       1,904           MEDIUM

  features/assistant.py                 1,904           MEDIUM

  core/db_manager.py                    1,712           MEDIUM
  -----------------------------------------------------------------------

Recommendation: Files exceeding 1,000 lines should be evaluated for
decomposition into smaller, focused modules.

### 2.2.2 Duplicate Authentication Systems

The codebase contains both legacy Supabase auth (auth/) and new V2 auth
(core/auth/). This creates maintenance overhead and potential security
inconsistencies.

-   Legacy: auth/service.py, auth/ui.py, auth/middleware.py

-   V2: core/auth/service.py, core/auth/invitation_service.py

Recommendation: Complete migration to V2 auth and remove legacy auth
module.

### 2.2.3 Debug Code in Production

Found 48+ instances of print() statements and DEBUG comments in core
modules. These should be replaced with proper logging.

### 2.2.4 Exception Handling Patterns

Multiple bare except: clauses found in postgres_manager.py that swallow
exceptions silently. This masks errors and complicates debugging.

# 3. Test Categories & Scope

## 3.1 Unit Tests

Purpose: Test individual functions and classes in isolation.

### 3.1.1 Core Module Tests

  -----------------------------------------------------------------------
  **Component**              **Test Focus**         **Priority**
  -------------------------- ---------------------- ---------------------
  DataHub                    Data loading, merging, CRITICAL
                             validation             

  DatabaseManager            CRUD operations, query CRITICAL
                             building               

  PostgresManager            Connection pooling,    CRITICAL
                             transactions           

  AuthService                Login, session,        CRITICAL
                             permissions            

  InvitationService          Invite creation,       HIGH
                             validation             

  ColumnMapper               Header detection,      HIGH
                             mapping                

  BulkValidation             Export validation      HIGH
                             rules                  
  -----------------------------------------------------------------------

### 3.1.2 Feature Module Tests

  -----------------------------------------------------------------------
  **Component**              **Test Focus**         **Priority**
  -------------------------- ---------------------- ---------------------
  Optimizer                  Bid calculations,      CRITICAL
                             recommendations        

  ImpactDashboard            Impact calculations,   CRITICAL
                             windowing              

  ReportCard                 Scoring algorithms,    HIGH
                             metrics                

  ExecutiveDashboard         Aggregations,          HIGH
                             visualizations         

  BulkExport                 File generation,       HIGH
                             validation             

  Assistant (AI)             Prompt handling,       MEDIUM
                             response parsing       
  -----------------------------------------------------------------------

### 3.1.3 Utility Tests

-   formatters.py: Currency, percentage, date formatting

-   matchers.py: Exact matching algorithms

-   validators.py: Input validation logic

-   metrics.py: Statistical calculations

## 3.2 Integration Tests

Purpose: Verify components work correctly together.

### 3.2.1 Database Integration

1.  Connection pool behavior under concurrent requests

2.  Transaction rollback on failures

3.  Data consistency across target_stats, actions_log tables

4.  Migration scripts execution (001-005)

5.  Index utilization for common queries

### 3.2.2 Authentication Flow

-   Login → Session creation → Permission check → Logout

-   Invitation creation → Email delivery → Acceptance → User creation

-   Password reset flow

-   Session timeout handling

### 3.2.3 Data Pipeline

-   File upload → Column mapping → Validation → Storage

-   Deduplication logic accuracy

-   Reaggregation after data updates

-   ASIN enrichment via Rainforest API

## 3.3 End-to-End Tests

Purpose: Simulate real user workflows.

### 3.3.1 Critical User Journeys

  -----------------------------------------------------------------------
  **Journey**                    **Test Steps**
  ------------------------------ ----------------------------------------
  New User Onboarding            Accept invite → Set password → Complete
                                 wizard → View dashboard

  Data Upload Flow               Upload STR → Map columns → Validate →
                                 View in optimizer

  Optimization Workflow          View recommendations → Filter/sort →
                                 Generate bulk file → Download

  Impact Analysis                Select account → View waterfall → Drill
                                 into decisions

  Report Generation              Configure report → Preview → Generate
                                 PDF/DOCX
  -----------------------------------------------------------------------

## 3.4 Performance Tests

Purpose: Ensure application scales under production load.

### 3.4.1 Load Scenarios

  ------------------------------------------------------------------------
  **Scenario**           **Concurrent       **Data Volume** **Target**
                         Users**                            
  ---------------------- ------------------ --------------- --------------
  Normal Load            10                 100K rows       \<3s response

  Peak Load              50                 500K rows       \<5s response

  Stress Test            100                1M rows         \<10s response

  Endurance              25                 24 hours        No memory
                                                            leaks
  ------------------------------------------------------------------------

### 3.4.2 Database Performance

-   Query execution time for target_stats with 1M+ rows

-   Connection pool exhaustion behavior

-   Index effectiveness analysis (EXPLAIN ANALYZE)

-   Bulk insert performance for data ingestion

### 3.4.3 Memory & Resource Tests

-   Streamlit session state growth over time

-   Pandas DataFrame memory with large datasets

-   Cache hit/miss ratios (@st.cache_data)

## 3.5 Security Tests

Purpose: Identify vulnerabilities and ensure data protection.

### 3.5.1 Authentication Security

-   Password hashing (bcrypt) verification

-   Session token randomness and expiration

-   Brute force protection (rate limiting)

-   Invitation token uniqueness and expiry

### 3.5.2 SQL Injection Prevention

-   Parameterized query usage in postgres_manager.py

-   Input sanitization for user-provided filters

-   Dynamic query construction audit

### 3.5.3 Data Access Control

-   Organization-level data isolation

-   Role-based permission enforcement

-   Cross-account data access prevention

# 4. Code Quality Audit Checklist

## 4.1 Structure & Organization

  ------------------------------------------------------------------------
  **Check Item**                            **Status**      **Priority**
  ----------------------------------------- --------------- --------------
  Single Responsibility Principle adherence PENDING         HIGH

  Module cohesion (related code grouped)    PENDING         HIGH

  Circular import detection                 PENDING         MEDIUM

  Dead code elimination                     PENDING         MEDIUM

  Consistent naming conventions             PENDING         MEDIUM

  Directory structure matches architecture  PENDING         MEDIUM
  ------------------------------------------------------------------------

## 4.2 Code Redundancy Analysis

  ------------------------------------------------------------------------
  **Check Item**                            **Status**      **Priority**
  ----------------------------------------- --------------- --------------
  Duplicate function definitions across     PENDING         HIGH
  modules                                                   

  Copy-pasted code blocks (\>20 lines)      PENDING         HIGH

  Similar SQL queries that could be         PENDING         MEDIUM
  parameterized                                             

  Repeated UI component patterns            PENDING         MEDIUM

  Duplicate auth implementations (legacy vs PENDING         HIGH
  V2)                                                       
  ------------------------------------------------------------------------

## 4.3 Technical Debt Items

  ------------------------------------------------------------------------
  **Check Item**                            **Status**      **Priority**
  ----------------------------------------- --------------- --------------
  TODO/FIXME/HACK comments resolution       48+ found       MEDIUM

  Debug print() statements removal          48+ found       HIGH

  Bare except: clauses replacement          PENDING         HIGH

  Hardcoded values extraction to config     PENDING         MEDIUM

  Archived code cleanup                     2 archives      LOW

  Unused imports removal                    PENDING         LOW
  ------------------------------------------------------------------------

## 4.4 Documentation Quality

  ------------------------------------------------------------------------
  **Check Item**                            **Status**      **Priority**
  ----------------------------------------- --------------- --------------
  Docstrings for public functions           PENDING         MEDIUM

  Type hints for function signatures        PENDING         MEDIUM

  README accuracy vs current codebase       PENDING         LOW

  API documentation completeness            PENDING         MEDIUM

  Architecture diagram currency             PENDING         LOW
  ------------------------------------------------------------------------

# 5. Test Implementation Plan

## 5.1 Test Framework Setup

Recommended test stack:

-   pytest: Primary test runner with fixtures and parametrization

-   pytest-cov: Code coverage reporting (target: 80%+)

-   pytest-mock: Mocking for external dependencies

-   hypothesis: Property-based testing for edge cases

-   locust: Load testing framework

-   bandit: Security vulnerability scanning

## 5.2 Test Directory Structure

Proposed reorganization:

**tests/**

├── unit/

│ ├── core/

│ ├── features/

│ └── utils/

├── integration/

│ ├── database/

│ ├── auth/

│ └── api/

├── e2e/

├── performance/

├── security/

├── fixtures/

└── conftest.py

## 5.3 Priority Test Cases

### 5.3.1 Critical Path Tests (Week 1)

1.  Impact calculation accuracy (decision_impact formulas)

2.  Bid recommendation logic validation

3.  Data deduplication correctness

4.  Authentication flow security

5.  Database transaction integrity

### 5.3.2 Data Integrity Tests (Week 2)

-   Column mapping variations (Amazon report format changes)

-   Currency conversion accuracy

-   Date range boundary conditions

-   Aggregation consistency across views

### 5.3.3 Edge Case Tests (Week 3)

-   Empty dataset handling

-   Zero-spend / zero-sales scenarios

-   Unicode in campaign names

-   Very large numeric values

-   Concurrent user session conflicts

# 6. Quality Metrics & Targets

  -----------------------------------------------------------------------
  **Metric**                     **Current**        **Target**
  ------------------------------ ------------------ ---------------------
  Unit Test Coverage             \~30% (estimated)  80%+

  Integration Test Coverage      \~20% (estimated)  70%+

  Cyclomatic Complexity (avg)    Unknown            \<10

  Code Duplication               Unknown            \<5%

  Security Vulnerabilities       Unknown            0 Critical/High

  P95 Response Time              Unknown            \<3 seconds

  Memory Usage (peak)            Unknown            \<2GB

  Database Query Time (p95)      Unknown            \<500ms
  -----------------------------------------------------------------------

# 7. Immediate Recommendations

## 7.1 Critical (Address Before Production)

-   Remove all debug print() statements and implement proper logging

-   Replace bare except: clauses with specific exception handling

-   Complete migration from legacy auth to V2 auth system

-   Add SQL injection prevention audit for dynamic queries

-   Implement rate limiting for authentication endpoints

## 7.2 High Priority (Within 2 Weeks)

-   Refactor impact_dashboard.py (4,082 lines) into smaller modules

-   Add comprehensive unit tests for optimizer calculations

-   Implement database connection health monitoring

-   Add input validation for all user-provided data

## 7.3 Medium Priority (Within 1 Month)

-   Add type hints to all public function signatures

-   Implement centralized error handling middleware

-   Add performance monitoring and alerting

-   Create CI/CD pipeline with automated testing

-   Clean up archived code directories

# 8. Implementation Timeline

  ------------------------------------------------------------------------
  **Week**        **Activities**                     **Deliverables**
  --------------- ---------------------------------- ---------------------
  Week 1          Critical path unit tests, security Test suite v1,
                  scan, debug cleanup                Security report

  Week 2          Integration tests, performance     Integration suite,
                  baseline, auth migration           Perf baseline

  Week 3          E2E tests, code refactoring,       E2E suite, Refactored
                  documentation                      modules

  Week 4          Load testing, final audit,         Final report,
                  production readiness review        Go/No-Go decision
  ------------------------------------------------------------------------

# Appendix A: Existing Test Inventory

Current test files in dev_resources/tests/:

  -----------------------------------------------------------------------
  **Test File**                             **Purpose**
  ----------------------------------------- -----------------------------
  test_invitation_system.py                 User invitation workflow
                                            validation

  test_prd_compliance.py                    PRD requirements validation

  test_phase1_compliance.py                 Phase 1 feature compliance

  test_executive_dashboard_integration.py   Dashboard integration tests

  test_ci_calculation.py                    Confidence interval
                                            calculations

  test_dedup.py                             Deduplication logic tests

  test_harvest_bulk.py                      Harvest bulk operations

  bulk_validation_spec.py                   Bulk validation
                                            specifications

  test_phase_3\_5_db_constraints.py         Database constraint tests

  test_phase_3\_5_logic.py                  Phase 3.5 logic validation
  -----------------------------------------------------------------------

# Appendix B: File Size Analysis

Files exceeding 1,000 lines (refactoring candidates):

  -----------------------------------------------------------------------
  **File Path**                         **Lines**   **Recommendation**
  ------------------------------------- ----------- ---------------------
  features/impact_dashboard.py          4,082       Split into
                                                    visualization,
                                                    calculation, data
                                                    modules

  features/optimizer.py                 2,662       Extract
                                                    recommendation logic
                                                    to separate class

  core/postgres_manager.py              2,586       Split by table/domain
                                                    (stats, actions,
                                                    users)

  features/executive_dashboard.py       1,904       Extract chart
                                                    builders to separate
                                                    module

  features/assistant.py                 1,904       Separate prompt
                                                    templates from logic

  core/db_manager.py                    1,712       Already abstracted by
                                                    PostgresManager

  features/report_card.py               1,754       Extract scoring
                                                    algorithms

  features/client_report.py             1,515       Separate PDF/DOCX
                                                    generation

  ppcsuite_v4_ui_experiment.py          1,518       Extract routing to
                                                    separate module
  -----------------------------------------------------------------------

*--- End of Document ---*
