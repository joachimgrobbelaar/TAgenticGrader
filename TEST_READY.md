# TEST_READY.md — Ulwazi Canvas SpeedGrader Test Harness & 4-Tier Test Suites

> **System**: Autonomous Canvas SpeedGrader Grading Agent (`PHYS1000` / Course `86326`)  
> **Milestone**: E2E Test Suite & Test Infrastructure Readiness  
> **Status**: **READY FOR DOWNSTREAM IMPLEMENTATION & AUDIT VERIFICATION**  
> **Date**: 2026-09-13  
> **Test Suite Pass Rate**: **185 / 185 PASSED (100%)**

---

## 1. Overview & Verification Strategy

The Ulwazi SpeedGrader Grading Agent test harness provides a hermetic, offline, contract-driven test infrastructure. It verifies all 16 core features defined in `PROJECT.md`, the 20-point laboratory rubrics from `memo_specifications.md`, and the dual REST/Playwright SpeedGrader interaction patterns from `speedgrader_architecture.md`.

### Key Verification Capabilities:
1. **Threaded Canvas Mock Server & Fixture Generator** (`tests/mock_server/`):
   - Lightweight in-process HTTP server running on an ephemeral port, simulating Canvas REST API endpoints and live SpeedGrader UI DOM pages.
   - Genuine PDF laboratory reports generated dynamically via PyMuPDF (`fitz`), online worksheet HTML bodies, and 2560x2184 Websnappr PNG code snapshots via `PIL`.
   - Complete 118-student Fri2 roster with Joachim Grobbelaar's allocated 35 students (`Fri2 28-62`, IDs `156944` to `190138`).
   - Built-in fault injection (rate limits, 401 unauthenticated, 500 errors, network latency, CSRF validation).
2. **Contract & Rubric Test Harness** (`tests/harness.py`):
   - Encodes authoritative data contracts (`CanvasSession`, `RawSubmission`, `ParsedSubmission`, `EvaluationResult`, `SubmissionReceipt`).
   - Implements reference evaluation engines for Exp05 (Thermal Expansion), Exp06 (Thin Lenses), and Lab 3 (Worksheet Parts A & B, Trinket/VPython Final Code).
   - Formats structured feedback comments matching Canvas SpeedGrader requirements.
3. **4-Tier Pytest Suite** (`tests/test_e2e_tier*.py`):
   - Comprehensive test cases spanning unit feature isolation, boundary conditions, cross-feature combinations, and full cohort scenarios.
4. **Headed Mode by Default Compliance**:
   - Conforms strictly to user directive: Headed mode default (`headless=False`), with `--headless` CLI toggle tested and verified.

---

## 2. 4-Tier Test Suite Inventory & Coverage Breakdown

| Tier | File | Target Count | Actual Tests | Pass Rate | Scope & Focus |
|:----:|:-----|:------------:|:------------:|:---------:|:--------------|
| **Tier 1** | `tests/test_e2e_tier1_features.py` | ≥ 80 | **81** | **100% (81/81)** | Happy-path coverage for all 16 features from `PROJECT.md` (5+ tests per feature). |
| **Tier 2** | `tests/test_e2e_tier2_boundaries.py` | ≥ 80 | **80** | **100% (80/80)** | Boundary, corner, and error cases: unsubmitted work, late submissions, malformed PDFs, 401/403/404/429/500 faults, units/sig-fig penalties, author idiosyncrasy tolerances. |
| **Tier 3** | `tests/test_e2e_tier3_combinations.py` | ≥ 16 | **16** | **100% (16/16)** | Pairwise cross-feature integration: Auth + REST, Navigation + Extraction, Extraction + Rubric, Rubric + Feedback + Posting + Next Student advancement. |
| **Tier 4** | `tests/test_e2e_tier4_scenarios.py` | ≥ 8 | **8** | **100% (8/8)** | Full real-world application scenarios: Exp05 e2e, Exp06 e2e, Lab3 Parts A/B/Code e2e, 35-student cohort batch run, multi-attachment merge, broken session recovery, and multi-URL headless runs. |
| **TOTAL** | | **≥ 184** | **185** | **100% (185/185)** | **Zero Failures, Zero Skips, 100% Hermetic** |

---

## 3. Feature Traceability Matrix (Features 1 through 16)

| # | Feature | Tier 1 (Happy) | Tier 2 (Boundary) | Tier 3 (Combos) | Tier 4 (Scenarios) |
|---|---------|:--------------:|:-----------------:|:---------------:|:------------------:|
| **F1** | Cookie & Session Extraction | 5 tests | 5 tests | Combo 1, 2, 16 | Scenario 1, 6, 8 |
| **F2** | SpeedGrader Navigation | 5 tests | 5 tests | Combo 2, 3, 5, 6, 16 | Scenario 1, 2, 8 |
| **F3** | Cohort Filtering (`Fri2 28-62`) | 5 tests | 5 tests | Combo 3, 4, 16 | Scenario 5, 8 |
| **F4** | Canvas REST Client | 5 tests | 5 tests | Combo 1, 4, 7, 8, 16 | Scenario 1–8 |
| **F5** | Exp05 PDF Report Extraction | 5 tests | 5 tests | Combo 5, 9, 16 | Scenario 1, 5, 7, 8 |
| **F6** | Exp06 PDF Report Extraction | 5 tests | 5 tests | Combo 6, 10 | Scenario 2, 8 |
| **F7** | Lab 3 Worksheet Extraction | 5 tests | 5 tests | Combo 7, 11 | Scenario 3, 8 |
| **F8** | Lab 3 Code / Snapshot Extraction | 5 tests | 5 tests | Combo 8, 11 | Scenario 3, 8 |
| **F9** | Exp05 Rubric Evaluation Engine | 5 tests | 5 tests | Combo 9, 12, 13, 16 | Scenario 1, 5, 7, 8 |
| **F10** | Exp06 Rubric Evaluation Engine | 5 tests | 5 tests | Combo 10, 12, 13 | Scenario 2, 8 |
| **F11** | Lab 3 Rubric Evaluation Engine | 5 tests | 5 tests | Combo 11 | Scenario 3, 8 |
| **F12** | Penalty & Tolerance Rules | 5 tests | 5 tests | Combo 12, 16 | Scenario 1, 2 |
| **F13** | Feedback Comment Generator | 5 tests | 5 tests | Combo 13, 14, 16 | Scenario 1–5, 8 |
| **F14** | SpeedGrader Grade & Comment Poster | 5 tests | 5 tests | Combo 14, 15, 16 | Scenario 1–5, 8 |
| **F15** | Next Student Transition | 5 tests | 5 tests | Combo 15, 16 | Scenario 5 |
| **F16** | Headless Autonomous CLI Runner | 6 tests | 5 tests | Combo 16 | Scenario 5, 8 |

---

## 4. Test Execution Guide

All tests run deterministically offline in the terminal sandbox using `pytest`.

### Run Entire 185-Test Suite:
```bash
pytest tests/
```

### Run Specific Tiers:
```bash
# Tier 1: Feature Isolation (81 tests)
pytest -v tests/test_e2e_tier1_features.py

# Tier 2: Boundary & Corner Cases (80 tests)
pytest -v tests/test_e2e_tier2_boundaries.py

# Tier 3: Pairwise Combinations (16 tests)
pytest -v tests/test_e2e_tier3_combinations.py

# Tier 4: Real-World Workload Scenarios (8 tests)
pytest -v tests/test_e2e_tier4_scenarios.py
```

### Fast Parallel Execution (if pytest-xdist available):
```bash
pytest -n auto tests/
```

---

## 5. Artifact Manifest

| Path | Purpose |
|---|---|
| `pytest.ini` | Root pytest configuration setting `pythonpath = .` and `testpaths = tests`. |
| `tests/conftest.py` | Session-scoped mock server fixture, client fixtures, and submission fixtures. |
| `tests/harness.py` | Data contracts, PDF/HTML extraction parsers, rubric engines, and grading client. |
| `tests/mock_server/server.py` | Threaded Canvas REST API and SpeedGrader UI HTTP mock server. |
| `tests/mock_server/data.py` | Assignments data, Joachim TA profile, and Fri2 student cohort roster. |
| `tests/mock_server/fixtures.py` | PyMuPDF PDF generators, HTML worksheet generators, and Websnappr PNG generators. |
| `tests/test_e2e_tier1_features.py` | 81 Tier 1 feature coverage test cases. |
| `tests/test_e2e_tier2_boundaries.py` | 80 Tier 2 boundary and error-handling test cases. |
| `tests/test_e2e_tier3_combinations.py` | 16 Tier 3 pairwise combination test cases. |
| `tests/test_e2e_tier4_scenarios.py` | 8 Tier 4 real-world application scenario test cases. |
| `TEST_READY.md` | Verification and execution reference document. |

---

## 6. Verification Gates for Downstream Agents

1. **Deterministic Execution**: All 185 tests execute without network access, third-party API dependencies, or live student data mutation.
2. **Opaque-Box Compatibility**: Tests interact strictly via public interfaces (`CanvasSession`, `RawSubmission`, `ParsedSubmission`, `EvaluationResult`, `CanvasGradingClient`, and HTTP endpoints), allowing downstream workers to implement internal modules freely while maintaining contract compatibility.
3. **Audit Readiness**: Test assertions verify exact mathematical formulas, error budgets, and tolerances specified in `memo_specifications.md`.
