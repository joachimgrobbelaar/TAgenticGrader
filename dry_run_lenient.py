#!/usr/bin/env python3
"""Dry-run grading with lenient rubrics: delete old comments, evaluate, report stats.

Usage:
    python dry_run_lenient.py [--delete-comments] [--headed]
"""
import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    ASSIGNMENTS, BASE_URL, COHORT_END_INDEX, COHORT_START_INDEX,
    COURSE_ID, EXP05_ASSIGNMENT_ID, EXP06_ASSIGNMENT_ID,
    LAB3_FINAL_CODE_ASSIGNMENT_ID, LAB3_PART_A_ASSIGNMENT_ID,
    LAB3_PART_B_ASSIGNMENT_ID, TA_NAME,
)
from src.api.client import CanvasAPIClient, CanvasAPIError
from src.auth.session import load_canvas_session
from src.cli import parse_cohort_students, resolve_evaluator
from src.extractor import parse_submission
from src.navigation.navigator import SpeedGraderNavigator
from src.submission.feedback import format_feedback_comment

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dry_run_lenient")

TA_USER_ID = 41165  # Joachim Grobbelaar

ALL_ASSIGNMENT_IDS = [
    EXP05_ASSIGNMENT_ID,
    EXP06_ASSIGNMENT_ID,
    LAB3_PART_A_ASSIGNMENT_ID,
    LAB3_PART_B_ASSIGNMENT_ID,
    LAB3_FINAL_CODE_ASSIGNMENT_ID,
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete-comments", action="store_true",
                        help="Delete all previously posted comments by the TA")
    parser.add_argument("--headed", action="store_true", default=True,
                        help="Show the browser (default: headed)")
    parser.add_argument("--headless", action="store_true", default=False)
    args = parser.parse_args()

    is_headless = args.headless and not args.headed

    # 1. Auth
    session = load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True)
    client = CanvasAPIClient(base_url=BASE_URL, session=session)
    logger.info("Session loaded.")

    # 2. Cohort
    cohort = parse_cohort_students("Fri2 28-62", client=client, course_id=COURSE_ID)
    logger.info("Cohort: %d students (indices %d-%d)", len(cohort),
                cohort[0].index, cohort[-1].index)

    # 3. Optional: delete old comments
    if args.delete_comments:
        logger.info("=== DELETING OLD COMMENTS ===")
        total_deleted = 0
        for aid in ALL_ASSIGNMENT_IDS:
            aname = ASSIGNMENTS.get(aid)
            aname = aname.name if aname else str(aid)
            for s in cohort:
                try:
                    n = client.delete_all_submission_comments(
                        COURSE_ID, aid, s.user_id, author_id=TA_USER_ID
                    )
                    if n > 0:
                        logger.info("  Deleted %d comments for %s on %s", n, s.name, aname)
                        total_deleted += n
                except Exception as e:
                    logger.warning("  Error deleting comments for %s: %s", s.name, e)
                time.sleep(0.1)
        logger.info("Total comments deleted: %d", total_deleted)

    # 4. Launch browser (headed)
    navigator = None
    if not is_headless:
        try:
            navigator = SpeedGraderNavigator(
                session=session, headless=False,
                base_url=BASE_URL, course_id=COURSE_ID,
            )
            navigator.start()
            logger.info("Headed browser launched.")
        except Exception as e:
            logger.warning("Could not launch browser: %s", e)

    # 5. Evaluate all students with lenient rubrics (DRY RUN - no posting)
    results = []  # list of dicts
    for aid in ALL_ASSIGNMENT_IDS:
        asgn = ASSIGNMENTS.get(aid)
        aname = asgn.name if asgn else f"Assignment {aid}"
        max_pts = asgn.points_possible if asgn else 20.0
        evaluator, extract_type = resolve_evaluator(aid)

        logger.info("=" * 60)
        logger.info("Evaluating: %s (ID: %d, Max: %.1f)", aname, aid, max_pts)
        logger.info("=" * 60)

        for idx, student in enumerate(cohort, 1):
            logger.info("[%d/%d] %s (ID: %d, Index: %d)",
                        idx, len(cohort), student.name, student.user_id, student.index)

            # Navigate SpeedGrader visually
            if navigator:
                try:
                    navigator.navigate_to_assignment(
                        assignment_id=aid, student_id=student.user_id,
                        wait_until="domcontentloaded",
                    )
                except Exception:
                    pass

            # Fetch submission
            raw_sub = {}
            try:
                raw_sub = client.get_assignment_submission(COURSE_ID, aid, student.user_id)
            except CanvasAPIError as e:
                logger.warning("  Fetch error: %s", e)

            wf = raw_sub.get("workflow_state", "unsubmitted")
            attachments = raw_sub.get("attachments", [])
            body_html = raw_sub.get("body", "")
            sub_url = raw_sub.get("url", "")

            if wf in ("unsubmitted", None) and not attachments and not body_html and not sub_url:
                score = 0.0
                feedback_lines = ["No submission."]
            else:
                try:
                    extracted = None
                    if aid in (EXP05_ASSIGNMENT_ID, EXP06_ASSIGNMENT_ID):
                        if attachments:
                            pdf_bytes = client.download_attachment(attachments[0]["url"])
                            extracted = parse_submission(pdf_bytes, assignment_type=extract_type)
                        else:
                            extracted = parse_submission(b"", assignment_type=extract_type)
                    elif aid in (LAB3_PART_A_ASSIGNMENT_ID, LAB3_PART_B_ASSIGNMENT_ID):
                        html = body_html or ""
                        if not html and attachments:
                            html = client.download_attachment(attachments[0]["url"]).decode("utf-8", errors="replace")
                        extracted = parse_submission(html, assignment_type=extract_type)
                    elif aid == LAB3_FINAL_CODE_ASSIGNMENT_ID:
                        code_input = sub_url or body_html or ""
                        if attachments and not code_input:
                            code_input = client.download_attachment(attachments[0]["url"]).decode("utf-8", errors="replace")
                        extracted = parse_submission(code_input, assignment_type=extract_type)

                    if extracted and hasattr(extracted, "boxes") and extract_type in ("lab3_part_a", "lab3_part_b"):
                        result = evaluator.evaluate(extracted.boxes)
                    elif extracted:
                        result = evaluator.evaluate(extracted)
                    else:
                        result = evaluator.evaluate({})

                    score = result.score
                    feedback_lines = result.feedback_lines
                except Exception as e:
                    logger.error("  Evaluation error: %s", e)
                    score = 0.0
                    feedback_lines = [f"Evaluation error: {e}"]

            logger.info("  Score: %.2f / %.1f", score, max_pts)

            results.append({
                "index": student.index,
                "student_id": student.user_id,
                "student_name": student.name,
                "assignment_id": aid,
                "assignment_name": aname,
                "score": score,
                "max_score": max_pts,
                "pct": round(100 * score / max_pts, 1) if max_pts > 0 else 0,
            })
            time.sleep(0.2)

    # Close browser
    if navigator:
        navigator.close()

    # 6. Write results
    out_dir = Path("artifacts")
    out_dir.mkdir(exist_ok=True)

    csv_path = out_dir / "dry_run_lenient.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)

    json_path = out_dir / "dry_run_lenient.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    # 7. Print statistics
    print("\n" + "=" * 70)
    print("DRY-RUN STATISTICS (Lenient Rubric)")
    print("=" * 70)

    for aid in ALL_ASSIGNMENT_IDS:
        asgn = ASSIGNMENTS.get(aid)
        aname = asgn.name if asgn else str(aid)
        max_pts = asgn.points_possible if asgn else 20.0
        scores = [r["score"] for r in results if r["assignment_id"] == aid]
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        avg_pct = 100 * avg / max_pts if max_pts > 0 else 0
        mn = min(scores)
        mx = max(scores)
        submitted = sum(1 for s in scores if s > 0)
        print(f"\n  {aname} (/{max_pts:.0f})")
        print(f"    Students: {len(scores)} | Submitted: {submitted}")
        print(f"    Average:  {avg:.2f} ({avg_pct:.1f}%)")
        print(f"    Range:    {mn:.2f} - {mx:.2f}")

    # Overall
    all_pcts = [r["pct"] for r in results if r["max_score"] > 0]
    if all_pcts:
        print(f"\n  OVERALL AVERAGE: {sum(all_pcts)/len(all_pcts):.1f}%")

    print("\n" + "=" * 70)
    print("\n  Per-student breakdown:")
    print(f"  {'Index':>5} {'ID':>8} {'Name':<30} {'Assignment':<45} {'Score':>6} {'%':>6}")
    print("  " + "-" * 102)
    for r in results:
        print(f"  {r['index']:>5} {r['student_id']:>8} {r['student_name']:<30} "
              f"{r['assignment_name'][:44]:<45} {r['score']:>5.1f} {r['pct']:>5.1f}%")

    print(f"\n  Results saved to: {csv_path} and {json_path}")
    print("  Review and confirm before running live submission.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
