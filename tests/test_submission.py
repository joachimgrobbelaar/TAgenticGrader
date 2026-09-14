"""
Unit and Integration Tests for Milestone 4: Grade Submission & Feedback Comment Engine.

Tests feedback formatting, dual submission channels (REST & Playwright UI),
SpeedGrader student advancement, dry-run safety modes, and local audit ledger logging.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from config import EXP05_ASSIGNMENT_ID, EXP06_ASSIGNMENT_ID
from src.api.client import CanvasAPIClient
from src.evaluator.base import EvaluationResult
from src.navigation.navigator import SpeedGraderNavigator
from src.submission import (
    GradePoster,
    SubmissionReceipt,
    format_feedback_comment,
    generate_feedback_comment,
    post_grade_and_comment,
)


# ==============================================================================
# 1. Feedback Comment Formatting Tests
# ==============================================================================
class TestFeedbackCommentFormatting:
    """Tests structured feedback comment generation according to physics lab rubric."""

    def test_header_and_assignment_info(self):
        result = EvaluationResult(
            score=18.5,
            max_score=20.0,
            breakdown={"Intro": 1.0, "Data": 4.0},
            feedback_lines=[],
        )
        comment = format_feedback_comment(
            result=result,
            assignment_name="EXP 05: Thermal Expansion",
            student_name="Sbongokuhle Mbizane",
        )

        assert (
            "[Automated Evaluation - PHYS1000/PHYS1033A Lab Grading System]" in comment
        )
        assert "Assignment: EXP 05: Thermal Expansion" in comment
        assert "Student: Sbongokuhle Mbizane" in comment
        assert "Total Score: 18.5 / 20.0" in comment

    def test_student_name_omitted_when_none(self):
        result = EvaluationResult(score=20.0, max_score=20.0, breakdown={"Total": 20.0})
        comment = format_feedback_comment(result=result, assignment_name="EXP 06")

        assert "Student:" not in comment
        assert "Assignment: EXP 06" in comment

    def test_itemized_rubric_breakdown(self):
        breakdown = {
            "Introduction": 1.0,
            "Objectives": 1.0,
            "Brass Table": 3.5,
            "Stainless Steel Table": 3.0,
            "Discussion": 1.0,
        }
        result = EvaluationResult(score=9.5, max_score=20.0, breakdown=breakdown)
        comment = format_feedback_comment(result=result, assignment_name="EXP 05")

        assert "Itemized Rubric Breakdown:" in comment
        assert "  - Introduction: 1.0 pts" in comment
        assert "  - Brass Table: 3.5 pts" in comment
        assert "  - Stainless Steel Table: 3.0 pts" in comment
        assert "  - Discussion: 1.0 pts" in comment

    def test_penalties_formatting(self):
        result = EvaluationResult(
            score=17.5,
            max_score=20.0,
            breakdown={"Report": 18.5},
            penalties_applied={"Units Omitted": 0.5, "Late Submission": 0.5},
        )
        comment = format_feedback_comment(result=result, assignment_name="EXP 05")

        assert "Penalties Applied:" in comment
        assert "  - Units Omitted: -0.5 pts" in comment
        assert "  - Late Submission: -0.5 pts" in comment

    def test_empty_penalties_header_omitted(self):
        result = EvaluationResult(score=20.0, max_score=20.0, breakdown={"All": 20.0})
        comment = format_feedback_comment(result=result, assignment_name="EXP 05")

        assert "Penalties Applied:" not in comment

    def test_feedback_lines_formatting(self):
        notes = [
            "Missing units in column Delta T.",
            "Optical lever derivation lacks factor of 2.",
            "Good discussion of systematic heat loss.",
        ]
        result = EvaluationResult(
            score=15.0,
            max_score=20.0,
            breakdown={"Total": 15.0},
            feedback_lines=notes,
        )
        comment = format_feedback_comment(result=result, assignment_name="EXP 05")

        assert "Feedback & Constructive Notes:" in comment
        for note in notes:
            assert f"  * {note}" in comment

    def test_empty_feedback_header_omitted(self):
        result = EvaluationResult(
            score=20.0, max_score=20.0, breakdown={"All": 20.0}, feedback_lines=[]
        )
        comment = format_feedback_comment(result=result, assignment_name="EXP 05")

        assert "Feedback & Constructive Notes:" not in comment

    def test_grader_signature_and_timestamp(self):
        ts = datetime(2026, 9, 13, 17, 30, 0, tzinfo=timezone.utc)
        result = EvaluationResult(score=19.0, max_score=20.0)
        comment = format_feedback_comment(
            result=result,
            assignment_name="EXP 05",
            grader_name="Joachim Grobbelaar",
            timestamp=ts,
        )

        assert "Graded by TA: Joachim Grobbelaar" in comment
        assert "Timestamp: 2026-09-13 17:30:00 UTC" in comment

    def test_special_characters_preservation(self):
        special_note = "Check alpha = (a*d)/(2*D*l0*Delta T) & Delta T <= 72 °C"
        result = EvaluationResult(
            score=18.0,
            max_score=20.0,
            breakdown={"Data": 4.0},
            feedback_lines=[special_note],
        )
        comment = format_feedback_comment(result=result, assignment_name="EXP 05")

        assert special_note in comment
        assert "°C" in comment

    def test_compatibility_alias_generate_feedback_comment(self):
        result = EvaluationResult(score=20.0, max_score=20.0, breakdown={"Intro": 1.0})
        c1 = format_feedback_comment(result, "EXP 05")
        c2 = generate_feedback_comment(result, "EXP 05")
        assert len(c1) > 0
        assert "Assignment: EXP 05" in c2
        assert "Total Score: 20.0 / 20.0" in c2
        assert "Graded by TA: Joachim Grobbelaar" in c2


# ==============================================================================
# 2. REST API Grade Submission Tests
# ==============================================================================
class TestGradePosterREST:
    """Tests REST API submission channel."""

    def test_submit_rest_calls_api_client(self, tmp_path):
        mock_api = MagicMock(spec=CanvasAPIClient)
        mock_api.submit_grade_and_comment.return_value = {
            "id": 12345,
            "score": 19.5,
            "workflow_state": "graded",
        }

        csv_path = tmp_path / "ledger.csv"
        json_path = tmp_path / "ledger.json"
        poster = GradePoster(
            api_client=mock_api,
            course_id=86326,
            ledger_path=csv_path,
            json_ledger_path=json_path,
        )

        receipt = poster.submit_rest(
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            score=19.5,
            comment="Excellent report.",
            student_name="Sbongokuhle Mbizane",
            assignment_name="EXP 05",
        )

        assert receipt.status == "graded"
        assert receipt.score == 19.5
        assert receipt.comment_posted is True
        assert receipt.method == "api"
        assert receipt.assignment_id == EXP05_ASSIGNMENT_ID
        assert receipt.user_id == 156944

        mock_api.submit_grade_and_comment.assert_called_once_with(
            course_id=86326,
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            score=19.5,
            comment="Excellent report.",
        )

    def test_submit_rest_with_live_mock_server(
        self, server_url, auth_session, tmp_path
    ):
        client = CanvasAPIClient(
            base_url=server_url,
            session_cookie="mock_authenticated_session_hash_abc123",
            csrf_token="mock_token",
        )
        csv_path = tmp_path / "test_ledger.csv"
        poster = GradePoster(api_client=client, course_id=86326, ledger_path=csv_path)

        result = EvaluationResult(
            score=18.0,
            max_score=20.0,
            breakdown={"Intro": 1.0, "Data": 4.0},
            feedback_lines=["Good data collection."],
        )
        receipt = poster.post_grade_and_comment(
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            result=result,
            assignment_name="EXP 05 Thermal Expansion",
            student_name="Sbongokuhle Mbizane",
            use_ui=False,
        )

        assert receipt.status == "graded"
        assert receipt.score == 18.0
        assert receipt.comment_posted is True

        # Verify submission state on mock server
        sub = client.get_assignment_submission(
            course_id=86326, assignment_id=EXP05_ASSIGNMENT_ID, user_id=156944
        )
        assert sub["score"] == 18.0
        assert sub["workflow_state"] == "graded"
        assert len(sub["submission_comments"]) >= 1
        last_comment = sub["submission_comments"][-1]["comment"]
        assert "Total Score: 18.0 / 20.0" in last_comment

    def test_missing_api_client_raises_error_for_rest(self):
        poster = GradePoster(api_client=None)
        with pytest.raises(RuntimeError, match="CanvasAPIClient must be provided"):
            poster.submit_rest(
                assignment_id=EXP05_ASSIGNMENT_ID,
                user_id=156944,
                score=18.0,
                comment="Test comment",
            )


# ==============================================================================
# 3. Dry-Run Safety Tests
# ==============================================================================
class TestDryRunSafety:
    """Tests dry-run mode safety guarantees: no modifications to remote state."""

    def test_rest_dry_run_does_not_mutate_remote_state(
        self, server_url, auth_session, tmp_path
    ):
        client = CanvasAPIClient(
            base_url=server_url,
            session_cookie="mock_authenticated_session_hash_abc123",
            csrf_token="mock_token",
        )
        csv_path = tmp_path / "dry_run_ledger.csv"
        poster = GradePoster(
            api_client=client,
            dry_run=True,
            course_id=86326,
            ledger_path=csv_path,
        )

        result = EvaluationResult(score=19.0, max_score=20.0, breakdown={"All": 19.0})
        receipt = poster.post_grade_and_comment(
            assignment_id=EXP06_ASSIGNMENT_ID,
            user_id=156944,
            result=result,
            use_ui=False,
        )

        assert receipt.status == "dry_run"
        assert receipt.score == 19.0
        assert receipt.comment_posted is False
        assert receipt.method == "dry_run"

        # Confirm remote Canvas submission is NOT altered
        sub = client.get_assignment_submission(
            course_id=86326, assignment_id=EXP06_ASSIGNMENT_ID, user_id=156944
        )
        assert sub["score"] is None
        assert sub["workflow_state"] == "submitted"

    def test_ui_dry_run_does_not_execute_dom_mutations(self, tmp_path):
        mock_navigator = MagicMock(spec=SpeedGraderNavigator)
        csv_path = tmp_path / "dry_run_ui_ledger.csv"
        poster = GradePoster(
            navigator=mock_navigator,
            dry_run=True,
            ledger_path=csv_path,
        )

        receipt = poster.submit_ui(
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            score=20.0,
            comment="Great work!",
        )

        assert receipt.status == "dry_run"
        assert receipt.comment_posted is False
        # Navigator methods should NOT be called
        mock_navigator.enter_grade.assert_not_called()
        mock_navigator.enter_comment.assert_not_called()
        mock_navigator.submit_comment.assert_not_called()


# ==============================================================================
# 4. Playwright UI Submission Channel Tests
# ==============================================================================
class TestGradePosterPlaywrightUI:
    """Tests browser DOM interaction channel via SpeedGraderNavigator."""

    def test_submit_ui_enters_grade_and_submits_comment(self, tmp_path):
        mock_navigator = MagicMock(spec=SpeedGraderNavigator)
        mock_navigator.enter_grade.return_value = True
        mock_navigator.enter_comment.return_value = True
        mock_navigator.submit_comment.return_value = True
        screenshot_file = str(tmp_path / "screenshots" / "graded_316697_156944.png")
        mock_navigator.take_screenshot.return_value = screenshot_file

        csv_path = tmp_path / "ui_ledger.csv"
        poster = GradePoster(
            navigator=mock_navigator,
            ledger_path=csv_path,
            grader_name="Joachim Grobbelaar",
        )

        result = EvaluationResult(
            score=17.5,
            max_score=20.0,
            breakdown={"Intro": 1.0, "Data": 4.0},
        )
        receipt = poster.post_grade_and_comment(
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            result=result,
            student_name="Sbongokuhle Mbizane",
            use_ui=True,
            screenshot_dir=tmp_path / "screenshots",
        )

        assert receipt.status == "graded"
        assert receipt.score == 17.5
        assert receipt.comment_posted is True
        assert receipt.method == "ui"
        assert receipt.screenshot_path == screenshot_file

        mock_navigator.navigate_to_assignment.assert_called_once_with(
            assignment_id=EXP05_ASSIGNMENT_ID, student_id=156944
        )
        mock_navigator.wait_for_speedgrader_ready.assert_called_once()
        mock_navigator.enter_grade.assert_called_once_with(score=17.5, press_enter=True)
        mock_navigator.enter_comment.assert_called_once()
        mock_navigator.submit_comment.assert_called_once()
        mock_navigator.take_screenshot.assert_called_once()

    def test_missing_navigator_raises_error_for_ui(self):
        poster = GradePoster(navigator=None)
        with pytest.raises(RuntimeError, match="SpeedGraderNavigator must be provided"):
            poster.submit_ui(
                assignment_id=EXP05_ASSIGNMENT_ID,
                user_id=156944,
                score=18.0,
                comment="Comment",
            )


# ==============================================================================
# 5. SpeedGrader Student Transition Tests
# ==============================================================================
class TestNextStudentTransition:
    """Tests advancing to next student in SpeedGrader."""

    def test_next_student_advances_and_returns_student_info(self):
        mock_navigator = MagicMock(spec=SpeedGraderNavigator)
        mock_navigator.next_student.return_value = True
        mock_navigator.get_current_student_info.return_value = {
            "student_name": "Imange Mdalana",
            "student_index": "29/118",
            "graded_count": "24/118",
            "current_url": "http://mock/speed_grader?student_id=192479",
        }

        poster = GradePoster(navigator=mock_navigator)
        info = poster.next_student(timeout_ms=5000)

        assert info["student_name"] == "Imange Mdalana"
        assert info["student_index"] == "29/118"
        assert info["transition_success"] is True
        mock_navigator.next_student.assert_called_once_with(timeout_ms=5000)

    def test_next_student_missing_navigator_raises_error(self):
        poster = GradePoster(navigator=None)
        with pytest.raises(RuntimeError, match="SpeedGraderNavigator must be provided"):
            poster.next_student()


# ==============================================================================
# 6. Audit Ledger Logging Tests
# ==============================================================================
class TestAuditLedgerLogging:
    """Tests local CSV and JSON receipts ledger recording."""

    def test_csv_ledger_recording(self, tmp_path):
        csv_file = tmp_path / "artifacts" / "grading_ledger.csv"
        mock_api = MagicMock(spec=CanvasAPIClient)
        mock_api.submit_grade_and_comment.return_value = {"status": "ok"}

        poster = GradePoster(api_client=mock_api, ledger_path=csv_file)

        receipt = poster.submit_rest(
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            score=19.0,
            comment="Feedback",
            student_name="Sbongokuhle Mbizane",
            assignment_name="EXP 05 Thermal Expansion",
        )

        assert receipt.status == "graded"
        assert csv_file.is_file()
        content = csv_file.read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        assert len(lines) == 2  # Header + 1 record
        header = lines[0]
        assert (
            "timestamp,assignment_id,assignment_name,user_id,student_name,score,status,comment_posted,method,screenshot_path"
            == header
        )
        row = lines[1]
        assert (
            "316697,EXP 05 Thermal Expansion,156944,Sbongokuhle Mbizane,19.0,graded,True,api"
            in row
        )

    def test_json_ledger_recording(self, tmp_path):
        json_file = tmp_path / "artifacts" / "grading_ledger.json"
        mock_api = MagicMock(spec=CanvasAPIClient)
        mock_api.submit_grade_and_comment.return_value = {"status": "ok"}

        poster = GradePoster(
            api_client=mock_api,
            json_ledger_path=json_file,
            ledger_path=tmp_path / "dummy.csv",
        )

        poster.submit_rest(
            assignment_id=EXP06_ASSIGNMENT_ID,
            user_id=192479,
            score=20.0,
            comment="Flawless",
            student_name="Imange Mdalana",
            assignment_name="EXP 06 Thin Lenses",
        )

        assert json_file.is_file()
        with open(json_file, encoding="utf-8") as jf:
            records = json.load(jf)
        assert len(records) == 1
        rec = records[0]
        assert rec["assignment_id"] == EXP06_ASSIGNMENT_ID
        assert rec["user_id"] == 192479
        assert rec["score"] == 20.0
        assert rec["status"] == "graded"
        assert rec["student_name"] == "Imange Mdalana"

    def test_ledger_sequential_appending(self, tmp_path):
        csv_file = tmp_path / "ledger.csv"
        json_file = tmp_path / "ledger.json"
        mock_api = MagicMock(spec=CanvasAPIClient)
        mock_api.submit_grade_and_comment.return_value = {"status": "ok"}

        poster = GradePoster(
            api_client=mock_api,
            ledger_path=csv_file,
            json_ledger_path=json_file,
        )

        # First student
        poster.submit_rest(316697, 156944, 18.0, "Comment 1", "Student 1")
        # Second student
        poster.submit_rest(316697, 192479, 19.5, "Comment 2", "Student 2")

        # CSV check
        lines = csv_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3  # Header + 2 rows

        # JSON check
        with open(json_file, encoding="utf-8") as jf:
            records = json.load(jf)
        assert len(records) == 2
        assert records[0]["user_id"] == 156944
        assert records[1]["user_id"] == 192479


# ==============================================================================
# 7. Top-Level Function Interface Contract Compliance
# ==============================================================================
class TestTopLevelInterfaceCompliance:
    """Tests top-level post_grade_and_comment function contract compliance."""

    def test_top_level_post_grade_and_comment_contract(self, tmp_path):
        mock_api = MagicMock(spec=CanvasAPIClient)
        mock_api.submit_grade_and_comment.return_value = {"status": "ok"}

        result = EvaluationResult(
            score=16.5,
            max_score=20.0,
            breakdown={"Intro": 1.0, "Data": 3.5},
            feedback_lines=["Good start."],
        )

        receipt = post_grade_and_comment(
            assignment_id=EXP05_ASSIGNMENT_ID,
            user_id=156944,
            result=result,
            use_ui=False,
            assignment_name="EXP 05",
            api_client=mock_api,
            ledger_path=tmp_path / "contract_ledger.csv",
        )

        assert isinstance(receipt, SubmissionReceipt)
        assert receipt.status == "graded"
        assert receipt.score == 16.5
        assert receipt.comment_posted is True
        assert receipt.assignment_id == EXP05_ASSIGNMENT_ID
        assert receipt.user_id == 156944
        assert receipt.timestamp is not None
