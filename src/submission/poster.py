"""
Grade submission and feedback comment posting engine for Ulwazi Canvas SpeedGrader.

Supports dual submission channels (fast, atomic REST API and visible Playwright DOM UI),
next-student SpeedGrader transitions, dry-run safety modes, and local audit ledger logging.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ASSIGNMENTS, COURSE_ID, TA_NAME
from src.api.client import CanvasAPIClient
from src.evaluator.base import EvaluationResult
from src.navigation.navigator import SpeedGraderNavigator
from src.submission.feedback import format_feedback_comment

logger = logging.getLogger(__name__)


@dataclass
class SubmissionReceipt:
    """
    Receipt confirming grade and feedback comment submission status.

    Attributes:
        status: Submission status ('graded', 'dry_run', 'failed', 'partial').
        assignment_id: Target Canvas assignment ID.
        user_id: Canvas student user ID.
        score: Numeric score submitted or evaluated.
        comment_posted: True if comment was successfully posted.
        timestamp: ISO 8601 UTC timestamp of submission event.
        method: Submission channel used ('api', 'ui', 'dry_run').
        assignment_name: Human-readable name of the assignment.
        student_name: Optional name of the student.
        screenshot_path: Optional path to verification screenshot.
        details: Additional metadata or response payload from Canvas API.
    """

    status: str
    assignment_id: int
    user_id: int
    score: float
    comment_posted: bool
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    method: str = "api"
    assignment_name: str | None = None
    student_name: str | None = None
    screenshot_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class GradePoster:
    """
    Submits grades and comments to Canvas SpeedGrader via REST API or Playwright UI.

    Features:
        - REST API submission via Canvas LMS endpoint `PUT /submissions/:id`.
        - Playwright UI interaction (data-testid='grade-input', TinyMCE body, submit button).
        - SpeedGrader next student transition.
        - Dry-run safety mode (preview grade & comment without modifying Canvas).
        - Local CSV and JSON audit ledger logging.
    """

    def __init__(
        self,
        api_client: CanvasAPIClient | None = None,
        navigator: SpeedGraderNavigator | None = None,
        dry_run: bool = False,
        course_id: int = COURSE_ID,
        ledger_path: str | Path = "artifacts/grading_ledger.csv",
        json_ledger_path: str | Path | None = "artifacts/grading_ledger.json",
        grader_name: str = TA_NAME,
    ) -> None:
        self.api_client = api_client
        self.navigator = navigator
        self.dry_run = dry_run
        self.course_id = course_id
        self.ledger_path = Path(ledger_path)
        self.json_ledger_path = Path(json_ledger_path) if json_ledger_path else None
        self.grader_name = grader_name

    def _resolve_assignment_name(
        self, assignment_id: int, provided_name: str = ""
    ) -> str:
        """Resolve human-readable assignment name from config or fallback."""
        if provided_name:
            return provided_name
        if assignment_id in ASSIGNMENTS:
            return ASSIGNMENTS[assignment_id].name
        return f"Assignment {assignment_id}"

    def _log_to_ledger(self, receipt: SubmissionReceipt) -> None:
        """Append submission receipt to CSV and JSON audit ledgers."""
        # 1. CSV Ledger
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            file_exists = (
                self.ledger_path.is_file() and self.ledger_path.stat().st_size > 0
            )
            with open(self.ledger_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(
                        [
                            "timestamp",
                            "assignment_id",
                            "assignment_name",
                            "user_id",
                            "student_name",
                            "score",
                            "status",
                            "comment_posted",
                            "method",
                            "screenshot_path",
                        ]
                    )
                writer.writerow(
                    [
                        receipt.timestamp,
                        receipt.assignment_id,
                        receipt.assignment_name or "",
                        receipt.user_id,
                        receipt.student_name or "",
                        receipt.score,
                        receipt.status,
                        receipt.comment_posted,
                        receipt.method,
                        receipt.screenshot_path or "",
                    ]
                )
        except (OSError, csv.Error) as exc:
            logger.warning(
                "Failed to write to CSV ledger %s: %s", self.ledger_path, exc
            )

        # 2. JSON Ledger
        if self.json_ledger_path:
            try:
                self.json_ledger_path.parent.mkdir(parents=True, exist_ok=True)
                records: list[dict[str, Any]] = []
                if (
                    self.json_ledger_path.is_file()
                    and self.json_ledger_path.stat().st_size > 0
                ):
                    try:
                        with open(self.json_ledger_path, "r", encoding="utf-8") as jf:
                            data = json.load(jf)
                            if isinstance(data, list):
                                records = data
                            else:
                                records = [data]
                    except (OSError, json.JSONDecodeError):
                        records = []

                record = {
                    "timestamp": receipt.timestamp,
                    "assignment_id": receipt.assignment_id,
                    "assignment_name": receipt.assignment_name,
                    "user_id": receipt.user_id,
                    "student_name": receipt.student_name,
                    "score": receipt.score,
                    "status": receipt.status,
                    "comment_posted": receipt.comment_posted,
                    "method": receipt.method,
                    "screenshot_path": receipt.screenshot_path,
                    "details": receipt.details,
                }
                records.append(record)
                with open(self.json_ledger_path, "w", encoding="utf-8") as jf:
                    json.dump(records, jf, indent=2)
            except (OSError, TypeError) as exc:
                logger.warning(
                    "Failed to write to JSON ledger %s: %s", self.json_ledger_path, exc
                )

    def submit_rest(
        self,
        assignment_id: int,
        user_id: int,
        score: float,
        comment: str,
        student_name: str | None = None,
        assignment_name: str | None = None,
    ) -> SubmissionReceipt:
        """
        Submit grade and comment via direct Canvas REST API.

        Args:
            assignment_id: Target assignment ID.
            user_id: Student Canvas user ID.
            score: Numeric score.
            comment: Formatted comment string.
            student_name: Optional student name for ledger.
            assignment_name: Optional assignment name for ledger.

        Returns:
            SubmissionReceipt confirming operation.
        """
        resolved_name = self._resolve_assignment_name(
            assignment_id, assignment_name or ""
        )

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would submit grade %.2f and comment via REST for user %s on %s",
                score,
                user_id,
                resolved_name,
            )
            receipt = SubmissionReceipt(
                status="dry_run",
                assignment_id=assignment_id,
                user_id=user_id,
                score=score,
                comment_posted=False,
                method="dry_run",
                assignment_name=resolved_name,
                student_name=student_name,
                details={"dry_run": True, "comment_preview": comment[:120]},
            )
            self._log_to_ledger(receipt)
            return receipt

        if self.api_client is None:
            raise RuntimeError("CanvasAPIClient must be provided for REST submissions.")

        api_resp = self.api_client.submit_grade_and_comment(
            course_id=self.course_id,
            assignment_id=assignment_id,
            user_id=user_id,
            score=score,
            comment=comment,
        )

        receipt = SubmissionReceipt(
            status="graded",
            assignment_id=assignment_id,
            user_id=user_id,
            score=score,
            comment_posted=True,
            method="api",
            assignment_name=resolved_name,
            student_name=student_name,
            details=api_resp if isinstance(api_resp, dict) else {},
        )
        self._log_to_ledger(receipt)
        return receipt

    def submit_ui(
        self,
        assignment_id: int,
        user_id: int,
        score: float,
        comment: str,
        student_name: str | None = None,
        assignment_name: str | None = None,
        screenshot_dir: str | Path = "artifacts/screenshots",
    ) -> SubmissionReceipt:
        """
        Submit grade and comment via Playwright SpeedGrader DOM UI.

        Args:
            assignment_id: Target assignment ID.
            user_id: Student Canvas user ID.
            score: Numeric score.
            comment: Formatted comment string.
            student_name: Optional student name.
            assignment_name: Optional assignment name.
            screenshot_dir: Directory to save audit screenshot.

        Returns:
            SubmissionReceipt confirming UI interaction.
        """
        resolved_name = self._resolve_assignment_name(
            assignment_id, assignment_name or ""
        )

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would submit grade %.2f and comment via UI for user %s on %s",
                score,
                user_id,
                resolved_name,
            )
            receipt = SubmissionReceipt(
                status="dry_run",
                assignment_id=assignment_id,
                user_id=user_id,
                score=score,
                comment_posted=False,
                method="dry_run",
                assignment_name=resolved_name,
                student_name=student_name,
                details={"dry_run": True, "comment_preview": comment[:120]},
            )
            self._log_to_ledger(receipt)
            return receipt

        if self.navigator is None:
            raise RuntimeError(
                "SpeedGraderNavigator must be provided for UI submissions."
            )

        # Ensure page is navigated to student's SpeedGrader view
        self.navigator.navigate_to_assignment(
            assignment_id=assignment_id, student_id=user_id
        )
        self.navigator.wait_for_speedgrader_ready()

        # Fill score into grade input
        grade_ok = self.navigator.enter_grade(score=score, press_enter=True)

        # Fill comment into TinyMCE or textarea
        comment_ok = self.navigator.enter_comment(comment_text=comment)

        # Submit comment
        submit_ok = self.navigator.submit_comment()

        # Capture post-submission verification screenshot
        shot_dir = Path(screenshot_dir)
        shot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_file = shot_dir / f"graded_{assignment_id}_{user_id}.png"
        screenshot_path: str | None = None
        try:
            screenshot_path = self.navigator.take_screenshot(screenshot_file)
        except (RuntimeError, OSError) as exc:
            logger.warning("Failed to capture post-submission screenshot: %s", exc)

        overall_status = "graded" if (grade_ok and submit_ok) else "partial"

        receipt = SubmissionReceipt(
            status=overall_status,
            assignment_id=assignment_id,
            user_id=user_id,
            score=score,
            comment_posted=submit_ok,
            method="ui",
            assignment_name=resolved_name,
            student_name=student_name,
            screenshot_path=screenshot_path,
            details={
                "grade_entered": grade_ok,
                "comment_entered": comment_ok,
                "comment_submitted": submit_ok,
            },
        )
        self._log_to_ledger(receipt)
        return receipt

    def post_grade_and_comment(
        self,
        assignment_id: int,
        user_id: int,
        result: EvaluationResult,
        assignment_name: str = "",
        student_name: str | None = None,
        use_ui: bool = False,
        screenshot_dir: str | Path = "artifacts/screenshots",
    ) -> SubmissionReceipt:
        """
        Unified dispatch method for posting evaluation score and structured comment.

        Args:
            assignment_id: Target assignment ID.
            user_id: Canvas student ID.
            result: EvaluationResult from rubric evaluation.
            assignment_name: Optional assignment name.
            student_name: Optional student name.
            use_ui: True to use Playwright browser UI; False for REST API.
            screenshot_dir: Directory for UI verification screenshots.

        Returns:
            SubmissionReceipt.
        """
        resolved_name = self._resolve_assignment_name(assignment_id, assignment_name)
        comment_text = format_feedback_comment(
            result=result,
            assignment_name=resolved_name,
            student_name=student_name,
            grader_name=self.grader_name,
        )

        if use_ui:
            return self.submit_ui(
                assignment_id=assignment_id,
                user_id=user_id,
                score=result.score,
                comment=comment_text,
                student_name=student_name,
                assignment_name=resolved_name,
                screenshot_dir=screenshot_dir,
            )

        return self.submit_rest(
            assignment_id=assignment_id,
            user_id=user_id,
            score=result.score,
            comment=comment_text,
            student_name=student_name,
            assignment_name=resolved_name,
        )

    def next_student(self, timeout_ms: int = 10000) -> dict[str, Any]:
        """
        Advance SpeedGrader view to the next student.

        Args:
            timeout_ms: Maximum wait duration for student navigation.

        Returns:
            Dict containing active student info after transition.
        """
        if self.navigator is None:
            raise RuntimeError(
                "SpeedGraderNavigator must be provided for next_student."
            )

        success = self.navigator.next_student(timeout_ms=timeout_ms)
        info = self.navigator.get_current_student_info()
        info["transition_success"] = success
        return info


def post_grade_and_comment(
    assignment_id: int,
    user_id: int,
    result: EvaluationResult,
    use_ui: bool = False,
    assignment_name: str = "",
    student_name: str | None = None,
    dry_run: bool = False,
    api_client: CanvasAPIClient | None = None,
    navigator: SpeedGraderNavigator | None = None,
    course_id: int = COURSE_ID,
    ledger_path: str | Path = "artifacts/grading_ledger.csv",
    json_ledger_path: str | Path | None = "artifacts/grading_ledger.json",
    grader_name: str = TA_NAME,
    screenshot_dir: str | Path = "artifacts/screenshots",
) -> SubmissionReceipt:
    """
    Top-level convenience function conforming to PROJECT.md interface contracts.

    Evaluates and submits grades and comments to Canvas SpeedGrader via REST or UI.
    """
    poster = GradePoster(
        api_client=api_client,
        navigator=navigator,
        dry_run=dry_run,
        course_id=course_id,
        ledger_path=ledger_path,
        json_ledger_path=json_ledger_path,
        grader_name=grader_name,
    )
    return poster.post_grade_and_comment(
        assignment_id=assignment_id,
        user_id=user_id,
        result=result,
        assignment_name=assignment_name,
        student_name=student_name,
        use_ui=use_ui,
        screenshot_dir=screenshot_dir,
    )
