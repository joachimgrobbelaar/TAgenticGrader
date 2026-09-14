"""Autonomous CLI runner for Ulwazi Canvas SpeedGrader Grading Agent.

Provides command-line entrypoint for orchestrating the complete grading pipeline:
- Canvas authentication & session extraction
- Visible (headed) Playwright SpeedGrader browser automation
- Cohort filtering (Fri2 28-62, 35 students)
- Ingestion, extraction, rubric evaluation, and grade/comment submission
- Local CSV/JSON audit ledger logging and markdown summary reporting
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from config import (
    ASSIGNMENTS,
    BASE_URL,
    COHORT_END_INDEX,
    COHORT_GROUP_ID,
    COHORT_START_INDEX,
    COURSE_ID,
    EXP05_ASSIGNMENT_ID,
    EXP06_ASSIGNMENT_ID,
    HEADLESS,
    LAB3_FINAL_CODE_ASSIGNMENT_ID,
    LAB3_PART_A_ASSIGNMENT_ID,
    LAB3_PART_B_ASSIGNMENT_ID,
    TA_NAME,
    AssignmentConfig,
)
from src.api.client import CanvasAPIClient, CanvasAPIError
from src.auth.session import CanvasSession, load_canvas_session
from src.evaluator.base import BaseEvaluator, EvaluationResult
from src.evaluator.exp05_evaluator import Exp05Evaluator
from src.evaluator.exp06_evaluator import Exp06Evaluator
from src.evaluator.lab3_evaluator import (
    Lab3FinalCodeEvaluator,
    Lab3PartAEvaluator,
    Lab3PartBEvaluator,
)
from src.extractor import parse_submission
from src.extractor.base import ExtractedSubmission, RawSubmission
from src.navigation.cohort import (
    CohortStudent,
    filter_cohort_students,
    get_allocated_cohort,
    get_student_by_id,
)
from src.navigation.navigator import SpeedGraderNavigator
from src.submission.feedback import format_feedback_comment
from src.submission.poster import GradePoster, SubmissionReceipt

logger = logging.getLogger("ulwazi_grading_agent")

ASSIGNMENT_KEY_MAP: dict[str, int] = {
    "exp05": EXP05_ASSIGNMENT_ID,
    "exp_05": EXP05_ASSIGNMENT_ID,
    "thermal_expansion": EXP05_ASSIGNMENT_ID,
    "316697": EXP05_ASSIGNMENT_ID,
    "exp06": EXP06_ASSIGNMENT_ID,
    "exp_06": EXP06_ASSIGNMENT_ID,
    "thin_lenses": EXP06_ASSIGNMENT_ID,
    "316844": EXP06_ASSIGNMENT_ID,
    "lab3_a": LAB3_PART_A_ASSIGNMENT_ID,
    "lab3_part_a": LAB3_PART_A_ASSIGNMENT_ID,
    "part_a": LAB3_PART_A_ASSIGNMENT_ID,
    "315832": LAB3_PART_A_ASSIGNMENT_ID,
    "lab3_b": LAB3_PART_B_ASSIGNMENT_ID,
    "lab3_part_b": LAB3_PART_B_ASSIGNMENT_ID,
    "part_b": LAB3_PART_B_ASSIGNMENT_ID,
    "315833": LAB3_PART_B_ASSIGNMENT_ID,
    "lab3_code": LAB3_FINAL_CODE_ASSIGNMENT_ID,
    "lab3_final_code": LAB3_FINAL_CODE_ASSIGNMENT_ID,
    "final_code": LAB3_FINAL_CODE_ASSIGNMENT_ID,
    "315831": LAB3_FINAL_CODE_ASSIGNMENT_ID,
}

ALL_ASSIGNMENT_IDS: list[int] = [
    EXP05_ASSIGNMENT_ID,
    EXP06_ASSIGNMENT_ID,
    LAB3_PART_A_ASSIGNMENT_ID,
    LAB3_PART_B_ASSIGNMENT_ID,
    LAB3_FINAL_CODE_ASSIGNMENT_ID,
]


@dataclass
class GradingTaskRecord:
    """Record tracking result of a student grading operation."""

    cohort_index: int
    student_id: int
    student_name: str
    assignment_id: int
    assignment_name: str
    score: float
    max_score: float
    status: str
    method: str
    timestamp: str
    breakdown: dict[str, float]
    feedback_lines: list[str]
    comment: str
    screenshot_path: str | None = None
    warnings: list[str] | None = None


def resolve_evaluator(
    assignment_id: int, 
    memo_pdf: str | None = None,
    max_score: float = 100.0
) -> tuple[BaseEvaluator, str]:
    """Return the appropriate evaluator instance and extractor assignment_type key."""
    if memo_pdf:
        from src.evaluator.generic_evaluator import GenericMemoEvaluator
        return GenericMemoEvaluator(memo_pdf, target_max_score=max_score), "generic"
        
    if assignment_id == EXP05_ASSIGNMENT_ID:
        return Exp05Evaluator(target_max_score=20.0), "exp05"
    elif assignment_id == EXP06_ASSIGNMENT_ID:
        return Exp06Evaluator(target_max_score=20.0), "exp06"
    elif assignment_id == LAB3_PART_A_ASSIGNMENT_ID:
        return Lab3PartAEvaluator(target_max_score=7.0), "lab3_part_a"
    elif assignment_id == LAB3_PART_B_ASSIGNMENT_ID:
        return Lab3PartBEvaluator(target_max_score=9.0), "lab3_part_b"
    elif assignment_id == LAB3_FINAL_CODE_ASSIGNMENT_ID:
        return Lab3FinalCodeEvaluator(target_max_score=6.0), "lab3_final_code"
    else:
        # Generic fallback
        return Exp05Evaluator(target_max_score=20.0), "exp05"


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for grading agent."""
    parser = argparse.ArgumentParser(
        prog="ulwazi_grading_agent",
        description="Autonomous Canvas SpeedGrader grading agent for Joachim Grobbelaar (Fri2 28-62).",
    )

    parser.add_argument(
        "--assignment",
        "--assignment-id",
        dest="assignment",
        default="exp05",
        help="Target assignment to grade: exp05, exp06, lab3_a, lab3_b, lab3_code, all, or specific ID.",
    )

    parser.add_argument(
        "--memo-pdf",
        dest="memo_pdf",
        default=None,
        help="Path to a PDF memorandum to use for generic rubric evaluation.",
    )

    parser.add_argument(
        "--max-score",
        dest="max_score",
        type=float,
        default=100.0,
        help="Maximum score for the generic evaluation if using --memo-pdf.",
    )

    parser.add_argument(
        "--cohort",
        default="Fri2 28-62",
        help="Cohort name and index range to grade (default: 'Fri2 28-62', 35 students).",
    )

    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Preview grades and feedback comments without mutating Canvas (safe simulation mode).",
    )

    parser.add_argument(
        "--live",
        dest="live",
        action="store_true",
        default=False,
        help="Explicit flag to commit grades and feedback comments to Canvas.",
    )

    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default is headed visible mode per directive).",
    )

    parser.add_argument(
        "--headed",
        dest="headed",
        action="store_true",
        default=False,
        help="Run browser in headed visible mode (default).",
    )

    parser.add_argument(
        "--no-browser",
        dest="no_browser",
        action="store_true",
        default=False,
        help="Skip launching Playwright browser (API-only execution).",
    )

    parser.add_argument(
        "--use-ui",
        dest="use_ui",
        action="store_true",
        default=False,
        help="Submit grades and comments through the SpeedGrader DOM UI instead of REST API.",
    )

    parser.add_argument(
        "--single-student",
        dest="single_student",
        type=int,
        default=None,
        help="Process only a single student by Canvas user ID.",
    )

    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default="artifacts",
        help="Output directory for ledgers, summaries, and screenshots (default: artifacts/).",
    )

    parser.add_argument(
        "--course-id",
        dest="course_id",
        type=int,
        default=COURSE_ID,
        help=f"Canvas LMS course ID (default: {COURSE_ID}).",
    )

    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=BASE_URL,
        help=f"Canvas LMS base URL (default: {BASE_URL}).",
    )

    parser.add_argument(
        "--take-screenshots",
        dest="take_screenshots",
        action="store_true",
        default=True,
        help="Capture visual SpeedGrader screenshots for graded students.",
    )

    parser.add_argument(
        "-v", "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable detailed debug logging output.",
    )

    return parser


def parse_cohort_students(
    cohort_arg: str,
    client: CanvasAPIClient | None = None,
    course_id: int = COURSE_ID,
) -> list[CohortStudent]:
    """Resolve the allocated cohort roster based on CLI cohort string."""
    # Attempt to query live roster via REST API first
    live_cohort: list[CohortStudent] = []
    if client:
        try:
            users = client.get_group_users(COHORT_GROUP_ID, course_id)
            if users:
                filtered = filter_cohort_students(users)
                for u in filtered:
                    idx = u.get("cohort_index") or u.get("index", 0)
                    uid = u["id"]
                    name = u.get("name", "")
                    sname = u.get("sortable_name", name)
                    live_cohort.append(CohortStudent(index=idx, user_id=uid, name=name, sortable_name=sname))
        except Exception as exc:
            logger.debug("Live group roster query skipped (%s); falling back to static roster.", exc)

    if len(live_cohort) == 35:
        return live_cohort

    # Fallback to authoritative static allocation
    allocated = get_allocated_cohort()

    # Parse index range if specified, e.g. "28-62" or "Fri2 28-62"
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", cohort_arg)
    if m:
        start_idx = int(m.group(1))
        end_idx = int(m.group(2))
        return [s for s in allocated if start_idx <= s.index <= end_idx]

    return allocated


def generate_markdown_summary(
    records: list[GradingTaskRecord],
    output_path: Path,
    cohort_name: str,
    course_id: int,
    is_dry_run: bool,
    is_headed: bool,
    use_ui: bool,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """Generate comprehensive markdown summary report of the grading run."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_s = (end_time - start_time).total_seconds()

    total = len(records)
    graded_count = sum(1 for r in records if r.status in ("graded", "dry_run"))
    scores = [r.score for r in records if r.status in ("graded", "dry_run")]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0

    lines: list[str] = [
        "# Ulwazi Canvas SpeedGrader — Autonomous Grading Run Summary",
        "",
        f"- **Execution Timestamp**: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} to {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ({duration_s:.1f}s)",
        f"- **Course ID**: {course_id} (PHYS1000/PHYS1033A)",
        f"- **Teaching Assistant**: {TA_NAME} (User ID: 41165)",
        f"- **Cohort**: {cohort_name} ({len(records)} students processed)",
        f"- **Execution Mode**: {'Headed Browser (Visible)' if is_headed else 'Headless Browser'} | {'DRY-RUN (Safe Preview)' if is_dry_run else 'LIVE COMMIT (Grades Posted)'}",
        f"- **Submission Channel**: {'Playwright SpeedGrader DOM UI' if use_ui else 'Direct Canvas REST API'}",
        "",
        "## Performance & Score Metrics",
        "",
        f"- **Total Submissions Processed**: {total}",
        f"- **Successful Evaluations**: {graded_count}",
        f"- **Average Score**: {avg_score:.2f}",
        f"- **Score Range**: {min_score:.2f} to {max_score:.2f}",
        "",
        "## Cohort Student Evaluation Ledger",
        "",
        "| Index | Student ID | Student Name | Assignment | Score / Max | Status | Method | Feedback Preview |",
        "|:-----:|:----------:|:-------------|:-----------|:-----------:|:------:|:------:|:-----------------|",
    ]

    for r in records:
        short_fb = "; ".join(r.feedback_lines[:2]) if r.feedback_lines else "Full criteria satisfied"
        if len(short_fb) > 60:
            short_fb = short_fb[:57] + "..."
        clean_name = r.student_name.replace("|", "/")
        lines.append(
            f"| {r.cohort_index} | {r.student_id} | {clean_name} | {r.assignment_name} | "
            f"{r.score:.1f} / {r.max_score:.1f} | {r.status} | {r.method} | {short_fb} |"
        )

    lines.extend([
        "",
        "## Audit Trails & Artifacts",
        "",
        "- CSV Ledger: `grading_ledger.csv`",
        "- JSON Ledger: `grading_ledger.json`",
        "- SpeedGrader Screenshots: `screenshots/`",
        "",
        "---",
        f"*Report generated autonomously by Ulwazi SpeedGrader Agent on {datetime.now(timezone.utc).isoformat()}*",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved markdown summary report to %s", output_path)


def run_grading_pipeline(args: argparse.Namespace) -> int:
    """Execute the full autonomous SpeedGrader grading pipeline."""
    start_time = datetime.now(timezone.utc)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    csv_ledger_path = out_dir / "grading_ledger.csv"
    json_ledger_path = out_dir / "grading_ledger.json"
    summary_md_path = out_dir / "grading_summary.md"

    # Headless logic: Headed by default (headless=False)
    # If --headless is passed -> headless=True
    # If --headed is passed -> headless=False
    if args.headless:
        is_headless = True
    elif args.headed:
        is_headless = False
    else:
        is_headless = False  # Default headed per directive

    # Live vs Dry-run logic
    # If --live is explicitly set -> dry_run = False
    # If --dry-run is set -> dry_run = True
    # If neither is set, default to dry_run for safe preview unless live specified
    if args.live:
        is_dry_run = False
    else:
        is_dry_run = True

    logger.info("Initializing Ulwazi SpeedGrader Grading Agent...")
    logger.info("Mode: %s | %s", "HEADED" if not is_headless else "HEADLESS", "DRY-RUN" if is_dry_run else "LIVE")

    # 1. Resolve Target Assignment IDs
    asgn_arg = str(args.assignment).strip().lower()
    if asgn_arg == "all":
        target_assignment_ids = ALL_ASSIGNMENT_IDS
    elif asgn_arg in ASSIGNMENT_KEY_MAP:
        target_assignment_ids = [ASSIGNMENT_KEY_MAP[asgn_arg]]
    elif asgn_arg.isdigit() and int(asgn_arg) in ASSIGNMENTS:
        target_assignment_ids = [int(asgn_arg)]
    else:
        logger.warning("Unrecognized assignment '%s', defaulting to EXP 05.", asgn_arg)
        target_assignment_ids = [EXP05_ASSIGNMENT_ID]

    # 2. Authentication & Session State
    logger.info("Loading Canvas authentication session...")
    try:
        session = load_canvas_session(
            base_url=args.base_url,
            validate=False,
            fallback_to_mock=True,
        )
        logger.info("Canvas session loaded successfully (CSRF present: %s).", bool(session.csrf_token))
    except Exception as exc:
        logger.error("Failed to load Canvas session: %s", exc)
        return 1

    # 3. Canvas REST API Client
    client = CanvasAPIClient(
        base_url=args.base_url,
        session=session,
    )

    # 4. Cohort Roster Resolution
    logger.info("Resolving allocated cohort roster for '%s'...", args.cohort)
    cohort_students = parse_cohort_students(args.cohort, client=client, course_id=args.course_id)
    if args.single_student:
        target_student_id = int(args.single_student)
        matched = [s for s in cohort_students if s.user_id == target_student_id]
        if matched:
            cohort_students = matched
        else:
            cohort_students = [CohortStudent(index=0, user_id=target_student_id, name="Test Student", sortable_name="Student, Test")]
        logger.info("Single student override: User ID %d", target_student_id)

    logger.info("Cohort size: %d students (Indices %d to %d)", len(cohort_students), cohort_students[0].index if cohort_students else 0, cohort_students[-1].index if cohort_students else 0)

    # 5. Playwright SpeedGrader Navigator (Headed by default)
    navigator: SpeedGraderNavigator | None = None
    if not args.no_browser:
        logger.info("Launching SpeedGrader Chromium browser (headless=%s)...", is_headless)
        try:
            navigator = SpeedGraderNavigator(
                session=session,
                headless=is_headless,
                base_url=args.base_url,
                course_id=args.course_id,
            )
            navigator.start()
            logger.info("Browser initialized successfully.")
        except Exception as exc:
            logger.warning("Could not launch Playwright browser (%s); continuing in API-only mode.", exc)
            navigator = None

    # 6. Grade Poster
    poster = GradePoster(
        api_client=client,
        navigator=navigator,
        dry_run=is_dry_run,
        course_id=args.course_id,
        ledger_path=csv_ledger_path,
        json_ledger_path=json_ledger_path,
        grader_name=TA_NAME,
    )

    all_records: list[GradingTaskRecord] = []

    try:
        for aid in target_assignment_ids:
            asgn_config = ASSIGNMENTS.get(
                aid,
                AssignmentConfig(
                    id=aid,
                    name=f"Assignment {aid}",
                    points_possible=20.0,
                    submission_types=["online_upload"],
                    memo_path="",
                    speedgrader_url="",
                ),
            )
            evaluator, extract_type = resolve_evaluator(
                aid, memo_pdf=args.memo_pdf, max_score=args.max_score
            )
            logger.info("==================================================================")
            logger.info("Processing Assignment: %s (ID: %d, Max Points: %.1f)", asgn_config.name, aid, asgn_config.points_possible)
            logger.info("==================================================================")

            # In headed mode, load the assignment in SpeedGrader
            if navigator:
                try:
                    logger.info("Navigating SpeedGrader viewport to assignment %d...", aid)
                    navigator.navigate_to_assignment(assignment_id=aid, wait_until="domcontentloaded")
                except Exception as exc:
                    logger.warning("SpeedGrader navigation warning: %s", exc)

            # Process each student in cohort
            for student in cohort_students:
                logger.info(
                    "[%d/%d] Student %d (%s) - Index %d",
                    student.index - 27 if student.index >= 28 else 1,
                    len(cohort_students),
                    student.user_id,
                    student.name,
                    student.index,
                )

                # If navigator is running, visibly display the student in SpeedGrader
                screenshot_path: str | None = None
                if navigator:
                    try:
                        navigator.navigate_to_assignment(
                            assignment_id=aid,
                            student_id=student.user_id,
                            wait_until="domcontentloaded",
                        )
                        navigator.wait_for_speedgrader_ready(timeout_ms=5000)
                        if args.take_screenshots:
                            shot_file = screenshot_dir / f"student_{aid}_{student.user_id}.png"
                            navigator.take_screenshot(shot_file)
                            screenshot_path = str(shot_file)
                    except Exception as exc:
                        logger.debug("Browser student navigation warning: %s", exc)

                # Fetch submission via REST client
                raw_sub: dict[str, Any] = {}
                try:
                    raw_sub = client.get_assignment_submission(
                        course_id=args.course_id,
                        assignment_id=aid,
                        user_id=student.user_id,
                    )
                except CanvasAPIError as exc:
                    logger.warning("Could not fetch submission for student %d: %s", student.user_id, exc)

                wf_state = raw_sub.get("workflow_state", "unsubmitted")
                attachments = raw_sub.get("attachments", [])
                body_html = raw_sub.get("body", "")
                sub_url = raw_sub.get("url", "")

                # Evaluation result placeholder
                eval_res: EvaluationResult

                if wf_state in ("unsubmitted", None) and not attachments and not body_html and not sub_url:
                    # Missing submission
                    logger.info("  No submission recorded (workflow_state: %s). Assigning 0.0 pts.", wf_state)
                    eval_res = EvaluationResult(
                        score=0.0,
                        max_score=asgn_config.points_possible,
                        breakdown={"Submission": 0.0},
                        feedback_lines=["No submission found for this assignment."],
                    )
                else:
                    # Ingest and extract submission content
                    try:
                        extracted: ExtractedSubmission | None = None

                        if aid in (EXP05_ASSIGNMENT_ID, EXP06_ASSIGNMENT_ID):
                            # Laboratory report PDF
                            if attachments:
                                pdf_url = attachments[0]["url"]
                                logger.info("  Downloading report PDF: %s", attachments[0].get("display_name", "submission.pdf"))
                                pdf_bytes = client.download_attachment(pdf_url)
                                extracted = parse_submission(pdf_bytes, assignment_type=extract_type)
                            else:
                                extracted = parse_submission(b"", assignment_type=extract_type)

                        elif aid in (LAB3_PART_A_ASSIGNMENT_ID, LAB3_PART_B_ASSIGNMENT_ID):
                            # Online worksheet HTML or text
                            html_content = body_html or ""
                            if not html_content and attachments:
                                # Try downloading attachment if body is empty
                                attach_bytes = client.download_attachment(attachments[0]["url"])
                                html_content = attach_bytes.decode("utf-8", errors="replace")
                            extracted = parse_submission(html_content, assignment_type=extract_type)

                        elif aid == LAB3_FINAL_CODE_ASSIGNMENT_ID:
                            # Code submission (URL, Websnappr PNG, or body text)
                            code_input = sub_url or body_html or ""
                            if attachments and not code_input:
                                attach_bytes = client.download_attachment(attachments[0]["url"])
                                code_input = attach_bytes.decode("utf-8", errors="replace")
                            extracted = parse_submission(code_input, assignment_type=extract_type)

                        # Evaluate extracted content
                        if extracted and hasattr(extracted, "boxes") and extract_type in ("lab3_part_a", "lab3_part_b"):
                            eval_res = evaluator.evaluate(extracted.boxes)
                        elif extracted:
                            eval_res = evaluator.evaluate(extracted)
                        else:
                            eval_res = EvaluationResult(
                                score=0.0,
                                max_score=asgn_config.points_possible,
                                breakdown={"Parsing": 0.0},
                                feedback_lines=["Unable to parse submission."],
                            )

                    except Exception as exc:
                        logger.error("  Extraction/Evaluation error for student %d: %s", student.user_id, exc)
                        eval_res = EvaluationResult(
                            score=0.0,
                            max_score=asgn_config.points_possible,
                            breakdown={"Error": 0.0},
                            feedback_lines=[f"Automated evaluation encountered an error: {exc}"],
                        )

                logger.info("  Score: %.2f / %.1f", eval_res.score, eval_res.max_score)

                # Format constructive feedback comment
                comment_text = format_feedback_comment(
                    result=eval_res,
                    assignment_name=asgn_config.name,
                    student_name=student.name,
                    grader_name=TA_NAME,
                )

                # Submit grade and comment
                receipt: SubmissionReceipt
                try:
                    receipt = poster.post_grade_and_comment(
                        assignment_id=aid,
                        user_id=student.user_id,
                        result=eval_res,
                        assignment_name=asgn_config.name,
                        student_name=student.name,
                        use_ui=args.use_ui,
                        screenshot_dir=screenshot_dir,
                    )
                except Exception as exc:
                    logger.error("  Grade submission error: %s", exc)
                    receipt = SubmissionReceipt(
                        status="failed",
                        assignment_id=aid,
                        user_id=student.user_id,
                        score=eval_res.score,
                        comment_posted=False,
                        method="error",
                        assignment_name=asgn_config.name,
                        student_name=student.name,
                    )

                record = GradingTaskRecord(
                    cohort_index=student.index,
                    student_id=student.user_id,
                    student_name=student.name,
                    assignment_id=aid,
                    assignment_name=asgn_config.name,
                    score=eval_res.score,
                    max_score=eval_res.max_score,
                    status=receipt.status,
                    method=receipt.method,
                    timestamp=receipt.timestamp,
                    breakdown=eval_res.breakdown,
                    feedback_lines=eval_res.feedback_lines,
                    comment=comment_text,
                    screenshot_path=screenshot_path or receipt.screenshot_path,
                )
                all_records.append(record)

                # Brief pause between students for UI smoothness and rate limit respect
                time.sleep(0.3)

    finally:
        if navigator:
            logger.info("Closing Playwright browser session...")
            navigator.close()

    end_time = datetime.now(timezone.utc)

    # Generate Markdown Summary Report
    cohort_title = args.cohort
    generate_markdown_summary(
        records=all_records,
        output_path=summary_md_path,
        cohort_name=cohort_title,
        course_id=args.course_id,
        is_dry_run=is_dry_run,
        is_headed=not is_headless,
        use_ui=args.use_ui,
        start_time=start_time,
        end_time=end_time,
    )

    logger.info("==================================================================")
    logger.info("Autonomous Grading Run Complete!")
    logger.info("Evaluations: %d | CSV Ledger: %s | Summary: %s", len(all_records), csv_ledger_path, summary_md_path)
    logger.info("==================================================================")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for CLI execution."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    return run_grading_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
