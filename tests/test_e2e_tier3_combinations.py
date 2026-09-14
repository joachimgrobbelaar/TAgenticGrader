"""
Tier 3: Pairwise Combinatorial & Cross-Feature Test Suite.
Verifies integration between session auth, navigation, cohort filtering, REST API,
submission extraction, rubric evaluation, feedback generation, posting, and student transitions.
Requirement: ≥16 tests total.
"""

from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlparse
import pytest
import requests

from tests.harness import (
    CanvasGradingClient,
    CanvasSession,
    EvaluationResult,
    ParsedSubmission,
    RawSubmission,
    SubmissionReceipt,
    evaluate_exp05,
    evaluate_exp06,
    evaluate_lab3_final_code,
    evaluate_lab3_part_a,
    evaluate_lab3_part_b,
    generate_feedback_comment,
    parse_exp05_pdf,
    parse_exp06_pdf,
    parse_lab3_html,
)
from tests.mock_server import (
    ASSIGNMENTS,
    CURRENT_USER,
    FRI2_COHORT_DATA,
    JOACHIM_COHORT,
    REFERENCE_VPYTHON_CODE,
    create_exp05_pdf,
    create_exp06_pdf,
    create_lab3_part_a_html,
    create_lab3_part_b_html,
    create_websnappr_png,
)


class TestTier3CrossFeatureCombinations:
    """Tier 3 Pairwise Combinatorial Tests across Features F1 through F16."""

    def test_combo_01_auth_and_rest_client(self, grading_client: CanvasGradingClient):
        """Combination 1 (F1 + F4): Session cookies -> Authenticate REST client -> Verify TA user profile."""
        resp = requests.get(f"{grading_client.base_url}/api/v1/users/self", headers=grading_client._headers())
        assert resp.status_code == 200
        user = resp.json()
        assert user["id"] == CURRENT_USER["id"]
        assert user["name"] == "Joachim Grobbelaar"
        assert any(e["role"] == "TaEnrollment" for e in user["enrollments"])

    def test_combo_02_auth_and_speedgrader_navigation(self, server_url: str, auth_session: CanvasSession):
        """Combination 2 (F1 + F2): Session cookies -> Deep-link navigation -> SpeedGrader DOM verification."""
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        assert 'data-testid="grade-input"' in resp.text
        assert 'id="comment_submit_button"' in resp.text
        assert 'data-testid="next-student-button"' in resp.text

    def test_combo_03_cohort_filter_and_speedgrader_navigation(self, server_url: str):
        """Combination 3 (F3 + F2): Filter cohort indices 28-62 -> Construct SpeedGrader deep-links."""
        cohort = [s for s in FRI2_COHORT_DATA if 28 <= s["index"] <= 62]
        assert len(cohort) == 35

        for student in cohort[:5]:  # Test first 5 deep links
            uid = student["id"]
            url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id={uid}"
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            assert params["student_id"] == [str(uid)]
            assert params["assignment_id"] == ["316697"]

    def test_combo_04_rest_client_and_cohort_filtering(self, grading_client: CanvasGradingClient):
        """Combination 4 (F4 + F3): Query group users -> Filter cohort -> Verify individual student submissions."""
        resp = requests.get(f"{grading_client.base_url}/api/v1/courses/86326/groups/144689/users")
        all_users = resp.json()
        joachim_students = [u for u in all_users if 28 <= u["index"] <= 62]

        for s in joachim_students[:3]:
            sub = grading_client.get_submission(assignment_id=316697, user_id=s["id"])
            assert sub.user_id == s["id"]
            assert sub.assignment_id == 316697

    def test_combo_05_navigation_and_exp05_extraction(self, grading_client: CanvasGradingClient):
        """Combination 5 (F2 + F5): SpeedGrader attachment link -> Download PDF -> Parse Exp05 report."""
        sub = grading_client.get_submission(assignment_id=316697, user_id=156944)
        attach_url = sub.attachments[0]["url"]
        pdf_bytes = grading_client.download_attachment(attach_url)

        parsed = parse_exp05_pdf(pdf_bytes)
        assert parsed.metadata["student_id"] == 156944
        assert parsed.numerical_values["brass_d"] == 6.1
        assert parsed.numerical_values["ss_d"] == 5.1

    def test_combo_06_navigation_and_exp06_extraction(self, grading_client: CanvasGradingClient):
        """Combination 6 (F2 + F6): SpeedGrader attachment link -> Download PDF -> Parse Exp06 report."""
        sub = grading_client.get_submission(assignment_id=316844, user_id=156944)
        attach_url = sub.attachments[0]["url"]
        pdf_bytes = grading_client.download_attachment(attach_url)

        parsed = parse_exp06_pdf(pdf_bytes)
        assert parsed.numerical_values["method1_v"] == 11.5
        assert parsed.tables["method2_row_count"] == 6
        assert parsed.numerical_values["method2_f"] == 12.0

    def test_combo_07_rest_client_and_lab3_worksheet_extraction(self, grading_client: CanvasGradingClient):
        """Combination 7 (F4 + F7): REST API submission query -> Extract HTML body -> Parse worksheet boxes."""
        sub = grading_client.get_submission(assignment_id=315832, user_id=156944)
        assert sub.submission_type == "online_text_entry"
        assert sub.body_html is not None

        boxes = parse_lab3_html(sub.body_html)
        assert len(boxes) >= 7
        assert "straight line" in boxes[1].lower()
        assert "33" in boxes[3]

    def test_combo_08_rest_client_and_lab3_code_extraction(self, grading_client: CanvasGradingClient):
        """Combination 8 (F4 + F8): Query final code submission -> Download Websnappr PNG -> Verify structure."""
        sub = grading_client.get_submission(assignment_id=315831, user_id=156944)
        assert sub.submission_type == "online_url"
        assert len(sub.attachments) >= 1

        png_bytes = grading_client.download_attachment(sub.attachments[0]["url"])
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    def test_combo_09_exp05_extraction_and_rubric_engine(self, sample_exp05_pdf: bytes):
        """Combination 9 (F5 + F9): Extract Exp05 text & tables -> Evaluate rubric -> Compute score."""
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        assert result.score == 20.0
        assert result.breakdown["Brass Table"] == 3.5
        assert result.breakdown["Stainless Steel Table"] == 3.5
        assert result.breakdown["Linear Expansion Coefficients"] == 3.0

    def test_combo_10_exp06_extraction_and_rubric_engine(self, sample_exp06_pdf: bytes):
        """Combination 10 (F6 + F10): Extract Exp06 data -> Evaluate rubric across Methods 1-3 -> Compute score."""
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.score == 20.0
        assert result.breakdown["Method 1"] == 1.0
        assert result.breakdown["Method 2"] == 7.0
        assert result.breakdown["Method 3"] == 5.0

    def test_combo_11_lab3_extraction_and_rubric_engine(self):
        """Combination 11 (F7 + F8 + F11): Extract Part A, Part B, and Code -> Score components."""
        boxes_a = parse_lab3_html(create_lab3_part_a_html())
        res_a = evaluate_lab3_part_a(boxes_a)
        assert res_a.score == 7.0

        boxes_b = parse_lab3_html(create_lab3_part_b_html())
        res_b = evaluate_lab3_part_b(boxes_b)
        assert res_b.score == 9.0

        res_code = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE)
        assert res_code.score == 6.0

        total_lab3 = res_a.score + res_b.score + res_code.score
        assert total_lab3 == 22.0

    def test_combo_12_rubric_engine_and_penalty_rules(self):
        """Combination 12 (F9 + F12): Evaluate Exp05 with omitted units -> Apply penalty deductions."""
        pdf_no_units = create_exp05_pdf(omit_units=True)
        parsed = parse_exp05_pdf(pdf_no_units)
        result = evaluate_exp05(parsed)
        assert "Units Omitted" in result.penalties_applied
        assert result.penalties_applied["Units Omitted"] == 0.5
        assert result.score == 19.5

    def test_combo_13_rubric_engine_and_feedback_generator(self, sample_exp05_pdf: bytes):
        """Combination 13 (F9 + F13): Rubric result -> Format structured feedback comment."""
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        res = evaluate_exp05(parsed)
        comment = generate_feedback_comment(res, "EXP 05: Thermal Expansion")
        assert "Total Score: 20.0 / 20.0" in comment
        assert "Brass Table: 3.5 pts" in comment
        assert "Introduction: 1.0 pts" in comment

    def test_combo_14_feedback_generator_and_grade_poster(self, grading_client: CanvasGradingClient, sample_exp05_pdf: bytes):
        """Combination 14 (F13 + F14): Format comment -> Post score and comment via REST API -> Verify."""
        res = evaluate_exp05(parse_exp05_pdf(sample_exp05_pdf))
        receipt = grading_client.post_grade_and_comment(
            assignment_id=316697, user_id=156944, result=res, assignment_name="EXP 05 Thermal Expansion"
        )
        assert receipt.status == "graded"
        assert receipt.score == 20.0

        sub = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert sub.score == 20.0
        assert len(sub.attachments) >= 1

    def test_combo_15_grade_poster_and_next_student_transition(self, grading_client: CanvasGradingClient):
        """Combination 15 (F14 + F15): Grade student 28 -> advance to student 29 -> Grade student 29."""
        # Student 28: Sbongokuhle Mbizane (156944)
        res_28 = EvaluationResult(score=18.5, max_score=20.0, breakdown={"Total": 18.5})
        receipt_28 = grading_client.post_grade_and_comment(316697, 156944, res_28, "EXP 05")
        assert receipt_28.score == 18.5

        # Transition to Student 29: Imange Mdalana (192479)
        res_29 = EvaluationResult(score=19.0, max_score=20.0, breakdown={"Total": 19.0})
        receipt_29 = grading_client.post_grade_and_comment(316697, 192479, res_29, "EXP 05")
        assert receipt_29.score == 19.0

        sub_28 = grading_client.get_submission(316697, 156944)
        sub_29 = grading_client.get_submission(316697, 192479)
        assert sub_28.score == 18.5
        assert sub_29.score == 19.0

    def test_combo_16_full_autonomous_grading_pipeline_cycle(self, grading_client: CanvasGradingClient):
        """Combination 16 (Full Pipeline): Auth -> Cohort -> Ingestion -> Evaluation -> Comment -> Post -> Audit."""
        # 1. Cohort
        student = JOACHIM_COHORT[0]
        uid = student["id"]
        aid = 316697

        # 2. Ingestion
        sub = grading_client.get_submission(assignment_id=aid, user_id=uid)
        pdf_bytes = grading_client.download_attachment(sub.attachments[0]["url"])

        # 3. Parsing & Evaluation
        parsed = parse_exp05_pdf(pdf_bytes)
        eval_res = evaluate_exp05(parsed)
        assert eval_res.score == 20.0

        # 4. Feedback & Posting
        receipt = grading_client.post_grade_and_comment(aid, uid, eval_res, "EXP 05 Thermal Expansion")
        assert receipt.status == "graded"

        # 5. Remote Audit
        sub_remote = grading_client.get_submission(assignment_id=aid, user_id=uid)
        assert sub_remote.score == 20.0
        assert sub_remote.workflow_state == "graded"
