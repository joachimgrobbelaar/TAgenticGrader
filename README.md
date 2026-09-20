# TAgenticGrader

**An autonomous AI grading agent for the Ulwazi (Canvas LMS) platform — PHYS1000, University of the Witwatersrand.**

TAgenticGrader automates the end-to-end grading pipeline for physics laboratory reports and computer lab worksheets. It downloads student submissions from Canvas SpeedGrader, extracts text from typed and handwritten/scanned PDFs, evaluates answers against a memo rubric, and posts rubric-breakdown comments and final grades back to Canvas — all without any manual intervention.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Structure](#repository-structure)
3. [How It Works — Step by Step](#how-it-works--step-by-step)
4. [Core Modules](#core-modules)
5. [Grading Pipeline Details](#grading-pipeline-details)
6. [Handwritten & Scanned Submission Handling](#handwritten--scanned-submission-handling)
7. [Configuration](#configuration)
8. [Running the Agent](#running-the-agent)
9. [Ad-Hoc Automation Scripts](#ad-hoc-automation-scripts)
10. [Testing](#testing)
11. [Assignment Coverage](#assignment-coverage)
12. [Tech Stack](#tech-stack)

---

## Architecture Overview

```
Canvas LMS (Ulwazi)
      │
      │  REST API (authenticated session)
      ▼
┌─────────────────────────────────────────────────────┐
│                  TAgenticGrader                     │
│                                                     │
│  ┌──────────┐   ┌────────────┐   ┌───────────────┐ │
│  │  Auth /  │──▶│  Canvas    │──▶│  Submission   │ │
│  │ Session  │   │ API Client │   │  Downloader   │ │
│  └──────────┘   └────────────┘   └───────────────┘ │
│                                         │           │
│                              ┌──────────▼─────────┐ │
│                              │   PDF Extractor    │ │
│                              │  (PyMuPDF / fitz)  │ │
│                              └──────────┬─────────┘ │
│                                         │           │
│                          ┌──────────────▼──────────┐│
│                          │  Has extractable text?  ││
│                          └──────┬───────────┬──────┘│
│                               YES           NO      │
│                          ┌────▼────┐   ┌────▼─────┐ │
│                          │  Text   │   │  Render  │ │
│                          │ Rubric  │   │ to PNG   │ │
│                          │Evaluator│   │(PyMuPDF) │ │
│                          └────┬────┘   └────┬─────┘ │
│                               │             │       │
│                               │        ┌────▼─────┐ │
│                               │        │ Vision AI│ │
│                               │        │ Subagent │ │
│                               │        │ (Pro LLM)│ │
│                               │        └────┬─────┘ │
│                          ┌────▼─────────────▼─────┐ │
│                          │    Score + Breakdown    │ │
│                          │   Capped to Max Score   │ │
│                          └────────────┬────────────┘ │
│                                       │             │
│                          ┌────────────▼────────────┐ │
│                          │  Canvas API PUT         │ │
│                          │  submission[posted_grade]│ │
│                          │  comment[text_comment]  │ │
│                          └─────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
TAgenticGrader/
│
├── config.py                        # Central config (URLs, course/assignment IDs, cohort groups)
├── run_agent.py                     # Main entry point — grades a single student interactively
├── run_regrade.py                   # Bulk regrade runner for specific cohort groups
│
├── src/
│   ├── api/
│   │   └── client.py                # Canvas REST API client (pagination, rate-limit, PUT grades)
│   ├── auth/
│   │   └── session.py               # Session loader — reads browser cookies for authentication
│   ├── cli.py                       # CLI interface (argparse wrappers)
│   ├── evaluator/
│   │   ├── base.py                  # BaseEvaluator + EvaluationResult dataclasses
│   │   ├── exp05_evaluator.py       # Rubric evaluator: Experiment 05 (Thermal Expansion)
│   │   ├── exp06_evaluator.py       # Rubric evaluator: Experiment 06 (Thin Spherical Lenses)
│   │   ├── lab3_evaluator.py        # Rubric evaluator: Computer Lab 3 (Part A + Part B)
│   │   └── generic_evaluator.py     # Fallback evaluator for unknown assignment types
│   ├── extractor/
│   │   ├── base.py                  # BaseExtractor + ExtractedPDFReport dataclasses
│   │   ├── pdf_extractor.py         # PDF text extraction via PyMuPDF (fitz)
│   │   ├── worksheet_extractor.py   # Field-by-field worksheet parser (box-level extraction)
│   │   └── code_extractor.py        # Trinket/Python code submission extractor
│   ├── navigation/
│   │   ├── cohort.py                # Group/cohort membership resolver
│   │   └── navigator.py             # SpeedGrader page navigator (legacy Playwright layer)
│   └── submission/
│       ├── feedback.py              # Markdown comment builder with rubric breakdown
│       └── poster.py                # Grade + comment submission via Canvas API
│
├── scripts/
│   └── ad_hoc_automation/           # One-off regrading and diagnostic scripts (see below)
│
├── grade_all_remaining.py           # Course-wide text PDF grader (all 1,379 students)
├── grade_all_final.py               # Course-wide Final Code auto-passer (Trinket shutdown)
├── render_and_generate.py           # Flat PDF renderer + Vision AI subagent JSON generator
├── render_and_generate_final.py     # Final sweep version of above
├── parse_and_push.py                # Transcript parser — syncs Vision AI results to Canvas
│
├── tests/
│   ├── conftest.py                  # Shared pytest fixtures
│   ├── harness.py                   # Integration test harness
│   ├── mock_server/                 # Local Canvas API mock server (Flask)
│   └── test_*.py                    # Unit + E2E test suites (4 tiers)
│
└── artifacts/
    └── lab3_downloads/              # Downloaded student submissions (PDFs, JPGs, PNGs)
```

---

## How It Works — Step by Step

### 1. Authentication
`src/auth/session.py` loads an authenticated Canvas session by reading the browser's saved cookies. This avoids the need for an API token and works with Ulwazi's SSO login. The session is passed to the API client for all subsequent requests.

### 2. Submission Discovery
`src/api/client.py` calls the Canvas REST API endpoint:
```
GET /api/v1/courses/{course_id}/assignments/{assignment_id}/submissions
    ?include[]=attachments&per_page=100
```
It handles pagination automatically (`include_all_pages=True`) to fetch all ~1,379 students.

### 3. File Download
For each student with an ungraded submission, the agent downloads their attachment (PDF, JPG, JPEG, HEIC, PNG) to `artifacts/lab3_downloads/{student_id}_{assignment_id}.{ext}`.

### 4. Content Extraction
`src/extractor/pdf_extractor.py` uses **PyMuPDF (fitz)** to extract text from PDFs. It parses the worksheet box-by-box using field label patterns and regex to isolate student answers for each rubric question.

### 5. Text vs. Image Decision
- **If text is found**: Proceed directly to the rubric evaluator.
- **If no text is found** (flat/scanned PDF or image submission): The PDF is rendered page-by-page to high-resolution `.png` files using `fitz.Page.get_pixmap()`, then routed to the Vision AI path.

### 6. Rubric Evaluation (Text Path)
Each assignment has a dedicated evaluator:
- `Lab3PartAEvaluator` — scores Boxes 1–7 (max 7.0 pts)
- `Lab3PartBEvaluator` — scores Boxes 8–17 (max 9.0 pts)
- `Exp05Evaluator` / `Exp06Evaluator` — for the lab experiment reports

Evaluators apply keyword matching, numerical range checks, and formula presence detection. Scoring is intentionally lenient, targeting a **~65% class average**.

### 7. Vision AI Evaluation (Handwritten/Scanned Path)
For submissions that cannot be text-extracted, the agent spawns concurrent **Vision AI subagents** (using a multimodal Pro-tier language model). Each subagent:
1. Receives the rendered PNG pages via `view_file`
2. Reads the handwritten content
3. Applies the same Box 1–17 rubric leniently
4. Returns a structured JSON result:
```json
{
  "part_a": { "score": 6.5, "breakdown": { "Box 1": 1.0, ... } },
  "part_b": { "score": 8.0, "breakdown": { "Box 8": 1.0, ... } }
}
```

Up to **38 subagents** are spawned concurrently for maximum throughput.

### 8. Grade Posting
Results are capped to the assignment maximum (7.0 / 9.0 / 6.0) and posted to Canvas via:
```
PUT /api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{student_id}
    submission[posted_grade] = <score>
    comment[text_comment]   = <markdown rubric breakdown>
```
The comment includes a per-box breakdown so students can see exactly where marks were awarded or deducted.

---

## Core Modules

### `src/api/client.py` — Canvas API Client
- Authenticated HTTP session via `requests.Session`
- Automatic pagination with `Link` header traversal
- Rate-limit backoff (429 handling)
- `get_assignment_submissions(course_id, assignment_id, include_all_pages)`
- `_request(method, endpoint, data)` — generic REST caller

### `src/extractor/pdf_extractor.py` — PDF Extractor
- Powered by **PyMuPDF (fitz)**
- Extracts raw text, then maps to named fields by section header detection
- Falls back to page-level text blocks if structured extraction fails
- Tolerates MuPDF rendering errors on corrupt/non-standard PDFs

### `src/evaluator/lab3_evaluator.py` — Lab 3 Evaluator
- `Lab3PartAEvaluator`: Evaluates Boxes 1–7 (data tables, unit conversions, uncertainty)
- `Lab3PartBEvaluator`: Evaluates Boxes 8–17 (circuit theory, Python code output, analysis)
- Scoring uses: keyword presence, numerical value checks, formula detection, partial credit

### `src/auth/session.py` — Session Manager
- Loads Ulwazi session cookies from browser profile or `.env`
- Validates session against `/api/v1/users/self`
- Falls back to mock mode for offline testing

---

## Grading Pipeline Details

### Computer Lab 3 (Assignment IDs: 315831, 315832, 315833)

| Component | Assignment ID | Max Score | Method |
|-----------|--------------|-----------|--------|
| Part A — Online Worksheet | 315832 | 7.0 | Text extraction → Rubric evaluator |
| Part B — Written Work | 315833 | 9.0 | Text extraction → Rubric evaluator / Vision AI |
| Final Code | 315831 | 6.0 | Auto-passed (Trinket.io shutdown Aug 2026) |

> **Note on Final Code**: Trinket.io was permanently shut down on 31 August 2026. All Trinket submission links became dead. To prevent unfair penalization, full marks (6.0/6.0) were awarded to all students who submitted, with an explanatory comment.

### Experiment 05 & 06 (Fri1 Group 144686, Fri2 Group 144689)
Lab reports graded against the official memo PDFs:
- `Exp05 - Thermal Expansion - Memo v2.pdf`
- `Exp06 - Thin Lenses - Memo.pdf`

Evaluators check for: correct experimental values, propagated uncertainties, graph descriptions, and conceptual answers.

---

## Handwritten & Scanned Submission Handling

Many students submit photos (`.jpg`, `.heic`, `.jpeg`) or scanned PDFs with no extractable text. The pipeline handles these as follows:

1. **Detection**: After PDF text extraction, if `raw_text.strip()` is empty → classified as image/flat.
2. **Rendering**: PyMuPDF renders each page at full resolution to `.png` files:
   ```python
   doc = fitz.open(path)
   for page_num in range(len(doc)):
       pix = doc.load_page(page_num).get_pixmap()
       pix.save(f"{base}_p{page_num}.png")
   ```
3. **Vision AI**: A `handwriting-grader` subagent receives the PNG file paths, uses `view_file` to read them visually, and applies the rubric from the image content.
4. **Result Sync**: `parse_and_push.py` reads the agent transcript, extracts the JSON result from each subagent's final message, maps it back to the student ID, caps scores, and PUTs to Canvas.

---

## Configuration

All configuration lives in `config.py`:

```python
BASE_URL   = "https://ulwazi.wits.ac.za"   # Canvas LMS instance
COURSE_ID  = 86326                           # PHYS1000 course

# Assignment IDs
LAB3_PART_A_ASSIGNMENT_ID = 315832
LAB3_PART_B_ASSIGNMENT_ID = 315833
LAB3_FINAL_ASSIGNMENT_ID  = 315831

# Teaching group IDs
FRI1_GROUP_ID = 144686
FRI2_GROUP_ID = 144689

# Grade targets
TARGET_AVG = 0.65   # 65% class average
```

Environment variable overrides:
```bash
export CANVAS_BASE_URL=https://ulwazi.wits.ac.za
export CANVAS_COURSE_ID=86326
export PLAYWRIGHT_HEADLESS=1
```

---

## Running the Agent

### Prerequisites
```bash
pip install -r requirements.txt
# Requires: PyMuPDF (fitz), requests, playwright, pytest
```

### Grade a single student
```bash
python run_agent.py --student-id 192424 --assignment lab3
```

### Bulk regrade a cohort
```bash
python run_regrade.py --group fri1
python run_regrade.py --group fri2
```

### Full course sweep (text PDFs)
```bash
python grade_all_remaining.py
```

### Full course sweep (Final Code)
```bash
python grade_all_final.py
```

### Render flat PDFs + generate Vision AI subagent configs
```bash
python render_and_generate_final.py
# Outputs: final_subagents.json
```

---

## Ad-Hoc Automation Scripts

Located in `scripts/ad_hoc_automation/`:

| Script | Purpose |
|--------|---------|
| `redo_all.py` | Full regrade sweep across all groups |
| `redo_fri1.py` | Regrade Fri1 cohort only |
| `resume_fri2.py` | Resume interrupted Fri2 grading |
| `regrade_typed.py` | Re-evaluate text submissions that scored 0 |
| `find_handwritten.py` | Identify image/flat-PDF submissions for Vision AI routing |
| `parse_subagents.py` | Parse Vision AI subagent transcripts and sync to Canvas |
| `parse_and_grade.py` | Combined parse + POST in one pass |
| `run_custom_cohorts.py` | Target arbitrary student ID lists |
| `clean_fri1_mistakes.py` | Correct over-scored entries from early runs |
| `test_eval.py` / `test_eval2.py` | Spot-check evaluator scoring against sample answers |
| `download_ncwane.py` | One-off download for specific student submissions |
| `grade_precious.py` / `grade_precious6.py` | Manual grade override scripts |

---

## Testing

The test suite uses a **local Flask mock server** that mirrors the Canvas REST API, allowing full end-to-end tests without touching the live LMS.

```bash
pytest tests/ -v
```

### Test Tiers

| Tier | File | Focus |
|------|------|-------|
| 1 | `test_e2e_tier1_features.py` | Core feature coverage (download, extract, evaluate, post) |
| 2 | `test_e2e_tier2_boundaries.py` | Edge cases (empty PDFs, 0-score, missing attachments) |
| 3 | `test_e2e_tier3_combinations.py` | Multi-assignment / multi-student combinations |
| 4 | `test_e2e_tier4_scenarios.py` | Real-world scenarios (handwritten, corrupt PDFs, retries) |
| Unit | `test_evaluators_unit.py` | Evaluator scoring accuracy |
| Unit | `test_extractor.py` | PDF extraction correctness |
| Unit | `test_submission.py` | Grade posting format validation |

---

## Assignment Coverage

| Assignment | Groups | Status |
|-----------|--------|--------|
| Experiment 05 — Thermal Expansion | Fri1, Fri2 (109–113, 1–31) | ✅ Complete |
| Experiment 06 — Thin Spherical Lenses | Fri1, Fri2 (109–113, 1–31) | ✅ Complete |
| Computer Lab 3 — Part A (315832) | All ~1,379 students | ✅ Complete |
| Computer Lab 3 — Part B (315833) | All ~1,379 students | ✅ Complete |
| Computer Lab 3 — Final Code (315831) | All ~1,379 students | ✅ Complete (auto-passed) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Canvas API | REST via `requests` |
| PDF Parsing | PyMuPDF (`fitz`) |
| Vision AI (OCR) | Multimodal Pro LLM (via Antigravity AI agent framework) |
| Browser Automation | Playwright (legacy navigation layer) |
| Testing | pytest + Flask mock server |
| Linting | Ruff |
| Version Control | Git / GitHub |

---

## Authors

- **Joachim Grobbelaar** — Teaching Assistant, PHYS1000, Wits University  
- Developed with assistance from **Antigravity AI** (Google DeepMind agentic coding assistant)

---

## License

Private repository — for internal academic use only. Not for public distribution.
