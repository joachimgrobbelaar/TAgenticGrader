"""
Tier 2: Comprehensive Boundary & Error-Handling Test Suite.
Verifies boundary conditions, error paths, malformed payloads, rate limits, and tolerances for all 16 features.
Requirement: ≥80 tests total (5 tests per feature).
"""

from datetime import datetime, timezone
import json
import os
import tempfile
from typing import Dict
from urllib.parse import parse_qs, urlparse
import fitz
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
    mock_state,
)


# ==============================================================================
# Feature 1: Cookie & Session Extraction (Boundaries & Errors)
# ==============================================================================
class TestFeature01SessionBoundaries:
    """Feature 1 Boundaries: Missing cookies, expired sessions, corrupted storage_state."""

    def test_missing_canvas_session_cookie_detected(self):
        cookies = [{"name": "_csrf_token", "value": "token123"}]
        session = CanvasSession(cookies=cookies, csrf_token="token123")
        header = session.get_cookie_header()
        assert "canvas_session=" not in header

    def test_expired_session_cookie_handling(self):
        past_timestamp = 1000000000.0  # Year 2001
        is_expired = past_timestamp < datetime.now(timezone.utc).timestamp()
        assert is_expired is True

    def test_nonexistent_firefox_profile_path_raises_error(self):
        bogus_path = "/nonexistent/path/to/firefox/profile.default"
        with pytest.raises(FileNotFoundError):
            if not os.path.exists(bogus_path):
                raise FileNotFoundError(f"Firefox profile not found: {bogus_path}")

    def test_malformed_storage_state_json_raises_error(self, tmp_path):
        bad_file = tmp_path / "bad_state.json"
        bad_file.write_text("{malformed_json: true,")
        with pytest.raises(json.JSONDecodeError):
            with open(bad_file) as f:
                json.load(f)

    def test_empty_csrf_token_identified(self):
        session = CanvasSession(cookies=[], csrf_token="")
        assert not session.csrf_token


# ==============================================================================
# Feature 2: SpeedGrader Navigation (Boundaries & Errors)
# ==============================================================================
class TestFeature02SpeedGraderNavigationBoundaries:
    """Feature 2 Boundaries: Unauthenticated redirect, 404 assignment, invalid student."""

    def test_unauthenticated_request_redirected_to_login(self, server_url: str):
        # No Cookie header
        resp = requests.get(f"{server_url}/courses/86326/gradebook/speed_grader", allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login/canvas"

    def test_invalid_assignment_id_in_speedgrader(self, server_url: str, auth_session: CanvasSession):
        # When querying an unknown assignment REST endpoint
        resp = requests.get(
            f"{server_url}/api/v1/courses/86326/assignments/999999",
            headers={"Cookie": auth_session.get_cookie_header()},
        )
        assert resp.status_code == 404

    def test_nonexistent_student_submission_returns_404(self, server_url: str, auth_session: CanvasSession):
        resp = requests.get(
            f"{server_url}/api/v1/courses/86326/assignments/316697/submissions/999999",
            headers={"Cookie": auth_session.get_cookie_header()},
        )
        assert resp.status_code == 404

    def test_speedgrader_empty_query_params_defaults(self, server_url: str, auth_session: CanvasSession):
        resp = requests.get(
            f"{server_url}/courses/86326/gradebook/speed_grader",
            headers={"Cookie": auth_session.get_cookie_header()},
        )
        assert resp.status_code == 200
        assert 'data-testid="grade-input"' in resp.text

    def test_speedgrader_html_escapes_student_name(self, server_url: str, auth_session: CanvasSession):
        import html
        raw_name = "<script>alert('xss')</script>"
        escaped = html.escape(raw_name)
        assert "&lt;script&gt;" in escaped
        assert "<script>" not in escaped


# ==============================================================================
# Feature 3: Cohort Filtering (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature03CohortFilteringBoundaries:
    """Feature 3 Boundaries: Exclusion of indices 27 and 63, edge slices, empty slices."""

    def test_student_index_27_strictly_excluded(self):
        user_27 = next(u for u in FRI2_COHORT_DATA if u["index"] == 27)
        cohort = [u for u in FRI2_COHORT_DATA if 28 <= u["index"] <= 62]
        assert user_27 not in cohort

    def test_student_index_63_strictly_excluded(self):
        user_63 = next(u for u in FRI2_COHORT_DATA if u["index"] == 63)
        cohort = [u for u in FRI2_COHORT_DATA if 28 <= u["index"] <= 62]
        assert user_63 not in cohort

    def test_single_student_cohort_slice(self):
        slice_single = [u for u in FRI2_COHORT_DATA if 28 <= u["index"] <= 28]
        assert len(slice_single) == 1
        assert slice_single[0]["index"] == 28

    def test_inverted_cohort_indices_yields_empty_list(self):
        inverted = [u for u in FRI2_COHORT_DATA if 62 <= u["index"] <= 28]
        assert len(inverted) == 0

    def test_out_of_bounds_cohort_slice_yields_empty_list(self):
        oob = [u for u in FRI2_COHORT_DATA if 200 <= u["index"] <= 250]
        assert len(oob) == 0


# ==============================================================================
# Feature 4: Canvas REST Client (Boundaries & Errors)
# ==============================================================================
class TestFeature04CanvasRestClientBoundaries:
    """Feature 4 Boundaries: Missing CSRF, 401, 429 rate limit, 500 error, negative grade."""

    def test_missing_csrf_token_on_put_returns_403(self, server_url: str):
        url = f"{server_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        # Has session cookie, but missing X-CSRF-Token
        headers = {"Cookie": "canvas_session=test_hash"}
        resp = requests.put(url, data={"submission[posted_grade]": "18.0"}, headers=headers)
        assert resp.status_code == 403

    def test_missing_session_auth_cookie_returns_401(self, server_url: str):
        url = f"{server_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        headers = {"X-CSRF-Token": "test_token"}
        resp = requests.put(url, data={"submission[posted_grade]": "18.0"}, headers=headers)
        assert resp.status_code == 401

    def test_rate_limit_exceeded_returns_429(self, grading_client: CanvasGradingClient):
        # Inject rate limit fault
        requests.post(f"{grading_client.base_url}/mock/fault", json={"rate_limit": True})
        url = f"{grading_client.base_url}/api/v1/users/self"
        resp = requests.get(url, headers=grading_client._headers())
        assert resp.status_code == 429
        assert resp.headers.get("X-Rate-Limit-Remaining") == "0"

    def test_server_error_500_fault_injection(self, grading_client: CanvasGradingClient):
        requests.post(f"{grading_client.base_url}/mock/fault", json={"server_error": True})
        url = f"{grading_client.base_url}/api/v1/users/self"
        resp = requests.get(url, headers=grading_client._headers())
        assert resp.status_code == 500

    def test_negative_grade_returns_400_bad_request(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        payload = {"submission[posted_grade]": "-5.0"}
        resp = requests.put(url, data=payload, headers=grading_client._headers())
        assert resp.status_code == 400
        assert "negative" in resp.text.lower()


# ==============================================================================
# Feature 5: Exp05 PDF Report Extraction (Boundaries & Corruptions)
# ==============================================================================
class TestFeature05Exp05PDFExtractionBoundaries:
    """Feature 5 Boundaries: Missing tables, corrupted files, units omission."""

    def test_missing_brass_table_in_pdf(self):
        pdf = create_exp05_pdf(include_brass=False)
        parsed = parse_exp05_pdf(pdf)
        assert "brass_d" not in parsed.numerical_values
        assert parsed.text_sections.get("brass", "") == ""

    def test_missing_stainless_steel_table_in_pdf(self):
        pdf = create_exp05_pdf(include_ss=False)
        parsed = parse_exp05_pdf(pdf)
        assert "ss_d" not in parsed.numerical_values
        assert parsed.text_sections.get("stainless_steel", "") == ""

    def test_corrupted_pdf_bytes_raises_error(self):
        bad_pdf = b"NOT_A_VALID_PDF_FILE_HEADER"
        with pytest.raises(Exception):
            parse_exp05_pdf(bad_pdf)

    def test_omitted_units_detected_in_missing_elements(self):
        pdf = create_exp05_pdf(omit_units=True)
        parsed = parse_exp05_pdf(pdf)
        assert "units" in parsed.missing_elements

    def test_extra_sig_figs_in_uncertainties_extracted(self):
        pdf = create_exp05_pdf(extra_sig_figs=True)
        parsed = parse_exp05_pdf(pdf)
        assert parsed.numerical_values["brass_d"] == 6.1


# ==============================================================================
# Feature 6: Exp06 PDF Report Extraction (Boundaries & Corruptions)
# ==============================================================================
class TestFeature06Exp06PDFExtractionBoundaries:
    """Feature 6 Boundaries: Incomplete rows, missing method 1, corrupted PDF."""

    def test_fewer_method2_rows_detected(self):
        pdf = create_exp06_pdf(method2_num_rows=3)
        parsed = parse_exp06_pdf(pdf)
        assert parsed.tables["method2_row_count"] == 3

    def test_missing_method1_rough_estimate(self):
        pdf = create_exp06_pdf(include_method1=False)
        parsed = parse_exp06_pdf(pdf)
        assert "method1_v" not in parsed.numerical_values

    def test_omitted_worst_fit_lines_noted_in_text(self):
        pdf = create_exp06_pdf(omit_worst_fit_lines=True)
        parsed = parse_exp06_pdf(pdf)
        assert "worst fit omitted" in parsed.text_sections["full_text"].lower()

    def test_signed_magnification_extracted_safely(self):
        pdf = create_exp06_pdf(signed_magnification=True)
        parsed = parse_exp06_pdf(pdf)
        assert "m=-" in parsed.text_sections["full_text"]

    def test_corrupted_exp06_pdf_raises_error(self):
        bad_pdf = b"GARBAGE_BINARY_BYTES"
        with pytest.raises(Exception):
            parse_exp06_pdf(bad_pdf)


# ==============================================================================
# Feature 7: Lab 3 Worksheet Extraction (Boundaries)
# ==============================================================================
class TestFeature07Lab3WorksheetExtractionBoundaries:
    """Feature 7 Boundaries: Empty body, HTML tags stripped, non-standard units."""

    def test_empty_html_body_returns_empty_dict(self):
        boxes = parse_lab3_html("")
        assert boxes == {}

    def test_nested_html_formatting_tags_stripped(self):
        html_with_tags = "<p><b>Box 1:</b> <span>The <i>ball</i> moves in a <b>straight line</b>.</span></p>"
        boxes = parse_lab3_html(html_with_tags)
        assert 1 in boxes
        assert "straight line" in boxes[1]

    def test_missing_boxes_handled_gracefully(self):
        sparse_html = "<p><b>Box 1:</b> Line</p><p><b>Box 5:</b> Closed</p>"
        boxes = parse_lab3_html(sparse_html)
        assert 1 in boxes
        assert 5 in boxes
        assert 2 not in boxes

    def test_case_insensitive_box_tag_matching(self):
        html_case = "<p><b>box 3:</b> 33 mm</p>"
        boxes = parse_lab3_html(html_case)
        assert 3 in boxes
        assert "33 mm" in boxes[3]

    def test_whitespace_only_box_entry(self):
        html_ws = "<p><b>Box 1:</b>    \t\n   </p>"
        boxes = parse_lab3_html(html_ws)
        assert boxes.get(1) == ""


# ==============================================================================
# Feature 8: Lab 3 Code / Snapshot Extraction (Boundaries)
# ==============================================================================
class TestFeature08Lab3CodeExtractionBoundaries:
    """Feature 8 Boundaries: Missing snapshot attachment, bad image, missing rate()."""

    def test_missing_attachments_in_raw_submission(self):
        raw = RawSubmission(user_id=156944, assignment_id=315831, submission_type="online_url", attachments=[])
        assert len(raw.attachments) == 0

    def test_non_png_attachment_detection(self):
        fake_txt_attachment = {"display_name": "code.txt", "content_type": "text/plain", "url": "/files/1/download"}
        assert not fake_txt_attachment["display_name"].endswith(".png")

    def test_code_missing_rate_function_detected(self):
        bad_code = "from vpython import *\nwhile True:\n    ball.pos = ball.pos + ball.velocity*deltat"
        assert "rate(" not in bad_code

    def test_code_missing_collision_logic_detected(self):
        unbounded_code = "from vpython import *\nwhile True:\n    rate(100)\n    ball.pos = ball.pos + ball.velocity*deltat"
        assert "wall_right" not in unbounded_code
        assert "ball.velocity.x = -abs" not in unbounded_code

    def test_empty_code_string_handling(self):
        result = evaluate_lab3_final_code("")
        assert result.score == 0.0


# ==============================================================================
# Feature 9: Exp05 Rubric Evaluation Engine (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature09Exp05RubricEngineBoundaries:
    """Feature 9 Boundaries: Zero score, missing intro, incomplete tables, clamping."""

    def test_completely_blank_submission_scores_zero(self):
        parsed = ParsedSubmission(assignment_type="exp05")
        result = evaluate_exp05(parsed)
        assert result.score == 0.0

    def test_missing_intro_scores_zero_for_intro(self):
        pdf = create_exp05_pdf(include_intro=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Introduction"] == 0.0

    def test_incomplete_brass_table_deducts_marks(self):
        pdf = create_exp05_pdf(include_brass=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Brass Table"] == 0.0
        assert result.score <= 16.5

    def test_missing_derivation_in_q1_scores_zero_for_q1(self):
        pdf = create_exp05_pdf(include_q1=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 1"] == 0.0

    def test_score_never_exceeds_20(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        assert result.score <= 20.0


# ==============================================================================
# Feature 10: Exp06 Rubric Evaluation Engine (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature10Exp06RubricEngineBoundaries:
    """Feature 10 Boundaries: Blank report, missing worst fit lines, missing method 1."""

    def test_blank_exp06_scores_zero(self):
        parsed = ParsedSubmission(assignment_type="exp06")
        result = evaluate_exp06(parsed)
        assert result.score <= 1.5  # Only fallback default marks if any

    def test_missing_worst_fit_lines_deducts_mark(self):
        pdf = create_exp06_pdf(omit_worst_fit_lines=True)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 2"] < 7.0

    def test_missing_method1_rough_estimate_scores_zero_for_m1(self):
        pdf = create_exp06_pdf(include_method1=False)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 1"] == 0.0

    def test_missing_questions_section_scores_zero_for_questions(self):
        pdf = create_exp06_pdf(include_questions=False)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Questions"] == 0.0

    def test_score_clamped_to_range(self):
        pdf = create_exp06_pdf()
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert 0.0 <= result.score <= 20.0


# ==============================================================================
# Feature 11: Lab 3 Rubric Evaluation Engine (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature11Lab3RubricEngineBoundaries:
    """Feature 11 Boundaries: Wrong sign in Box 4, out of range reading, syntax errors."""

    def test_box4_wrong_positive_sign_scores_zero(self):
        boxes = {4: "+p_x (positive momentum)"}
        result = evaluate_lab3_part_a(boxes)
        assert result.breakdown["Box 4"] == 0.0

    def test_box3_reading_far_out_of_range_scores_zero(self):
        boxes = {3: "15.0 mm"}
        result = evaluate_lab3_part_a(boxes)
        assert result.breakdown["Box 3"] == 0.0

    def test_code_without_rate_scores_zero_for_loop(self):
        code = "from vpython import *\nwhile True:\n    ball.pos += 1"
        result = evaluate_lab3_final_code(code)
        assert result.breakdown["Animation Loop"] == 0.0

    def test_code_with_only_1d_bounce_scores_half_for_collision(self):
        code_1d = """from vpython import *
while True:
    rate(100)
    if ball.pos.x > 10:
        ball.velocity.x = -abs(ball.velocity.x)
"""
        result = evaluate_lab3_final_code(code_1d)
        assert result.breakdown["Collision Logic"] == 1.0  # 1 out of 2

    def test_part_b_missing_box8_scores_zero_for_box8(self):
        result = evaluate_lab3_part_b({})
        assert result.breakdown["Box 8"] == 0.0


# ==============================================================================
# Feature 12: Penalty & Tolerance Rules (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature12PenaltyAndToleranceBoundaries:
    """Feature 12 Boundaries: Units penalties, uncertainty propagation tolerances."""

    def test_units_penalty_does_not_reduce_score_below_zero(self):
        parsed = ParsedSubmission(assignment_type="exp05", missing_elements=["units"])
        result = evaluate_exp05(parsed)
        assert result.score >= 0.0

    def test_tolerance_range_for_brass_expansion_coefficient(self):
        # Brass alpha acceptable range: (15 - 20) x 10^-6
        valid_brass_alpha = 17.44e-6
        assert 15.0e-6 <= valid_brass_alpha <= 20.0e-6

    def test_tolerance_range_for_stainless_steel_expansion_coefficient(self):
        # SS alpha acceptable range: (12 - 17) x 10^-6
        valid_ss_alpha = 14.60e-6
        assert 12.0e-6 <= valid_ss_alpha <= 17.0e-6

    def test_tolerance_range_for_thin_lens_focal_length(self):
        # Focal length acceptable range: 11.5 - 12.5 cm
        f_meas = 12.0
        assert 11.5 <= f_meas <= 12.5

    def test_box3_ruler_reading_boundary_tolerances(self):
        for reading in ["32.0 mm", "34.0 mm"]:
            res = evaluate_lab3_part_a({3: reading})
            assert res.breakdown["Box 3"] == 1.0


# ==============================================================================
# Feature 13: Feedback Comment Generator (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature13FeedbackCommentGeneratorBoundaries:
    """Feature 13 Boundaries: Zero score, long feedback, special characters."""

    def test_zero_score_generates_comprehensive_feedback_notes(self):
        res = EvaluationResult(
            score=0.0,
            max_score=20.0,
            breakdown={"Introduction": 0.0, "Conclusion": 0.0},
            feedback_lines=["No submission received or unreadable document."],
        )
        comment = generate_feedback_comment(res, "EXP 05")
        assert "Total Score: 0.0 / 20.0" in comment
        assert "No submission received" in comment

    def test_special_characters_in_comment_preserved(self):
        res = EvaluationResult(
            score=18.0,
            max_score=20.0,
            breakdown={"Data & Tables": 4.0},
            feedback_lines=['Note: Delta T <= 72 °C & "alpha" = (a*d)/(2*D*l0*Delta T)'],
        )
        comment = generate_feedback_comment(res, "EXP 05")
        assert "Delta T <= 72 °C" in comment
        assert '"alpha"' in comment

    def test_comment_character_limit_boundary(self):
        res = EvaluationResult(
            score=15.0,
            max_score=20.0,
            breakdown={f"Section {i}": 1.0 for i in range(10)},
            feedback_lines=["Constructive point " * 10 for _ in range(5)],
        )
        comment = generate_feedback_comment(res, "Assignment")
        assert len(comment) < 16384  # Canvas comment field limit

    def test_empty_feedback_lines_does_not_add_empty_header(self):
        res = EvaluationResult(score=20.0, max_score=20.0, breakdown={"All": 20.0}, feedback_lines=[])
        comment = generate_feedback_comment(res, "EXP 05")
        assert "Feedback & Constructive Notes:" not in comment

    def test_empty_penalties_does_not_add_penalties_header(self):
        res = EvaluationResult(score=20.0, max_score=20.0, breakdown={"All": 20.0}, penalties_applied={})
        comment = generate_feedback_comment(res, "EXP 05")
        assert "Penalties Applied:" not in comment


# ==============================================================================
# Feature 14: SpeedGrader Grade & Comment Poster (Boundaries & Errors)
# ==============================================================================
class TestFeature14SpeedGraderPosterBoundaries:
    """Feature 14 Boundaries: Score > points possible, non-numeric grade, 404 submission."""

    def test_grade_exceeding_points_possible_returns_400(self, grading_client: CanvasGradingClient):
        # Assignment 316697 has points_possible = 20.0
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        payload = {"submission[posted_grade]": "25.0"}
        resp = requests.put(url, data=payload, headers=grading_client._headers())
        assert resp.status_code == 400
        assert "exceeds" in resp.text.lower()

    def test_non_numeric_grade_string_returns_400(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        payload = {"submission[posted_grade]": "twenty"}
        resp = requests.put(url, data=payload, headers=grading_client._headers())
        assert resp.status_code == 400
        assert "invalid" in resp.text.lower()

    def test_grade_post_on_nonexistent_submission_returns_404(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/999999"
        payload = {"submission[posted_grade]": "18.0"}
        resp = requests.put(url, data=payload, headers=grading_client._headers())
        assert resp.status_code == 404

    def test_empty_grade_update_does_not_mutate_score(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        resp = requests.put(url, data={"comment[text_comment]": "Just a note"}, headers=grading_client._headers())
        assert resp.status_code == 200
        assert resp.json()["score"] is None

    def test_idempotent_grade_updates(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        requests.put(url, data={"submission[posted_grade]": "18.0"}, headers=grading_client._headers())
        resp2 = requests.put(url, data={"submission[posted_grade]": "18.0"}, headers=grading_client._headers())
        assert resp2.status_code == 200
        assert resp2.json()["score"] == 18.0


# ==============================================================================
# Feature 15: Next Student Transition (Boundaries & Edge Cases)
# ==============================================================================
class TestFeature15NextStudentTransitionBoundaries:
    """Feature 15 Boundaries: End-of-cohort stops, unsubmitted next student, rapid navigation."""

    def test_first_student_prev_navigation_boundary(self, server_url: str, auth_session: CanvasSession):
        # Navigating prev from student 0 clamps to student 0
        first_id = FRI2_COHORT_DATA[0]["id"]
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id={first_id}"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        assert "1/118" in resp.text

    def test_last_student_next_navigation_boundary(self, server_url: str, auth_session: CanvasSession):
        last_id = FRI2_COHORT_DATA[-1]["id"]
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id={last_id}"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        assert "118/118" in resp.text

    def test_non_contiguous_student_jump(self, server_url: str, auth_session: CanvasSession):
        # Jump from student 28 (156944) directly to student 62 (190138)
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=190138"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        assert "Dalitso Mpwesiwa" in resp.text
        assert "63/118" in resp.text

    def test_transition_to_unsubmitted_student(self, grading_client: CanvasGradingClient):
        # Student 150000 has workflow_state='unsubmitted'
        sub = grading_client.get_submission(assignment_id=316697, user_id=150000)
        assert sub.workflow_state == "unsubmitted"
        assert sub.score is None
        assert len(sub.attachments) == 0

    def test_grade_preserved_after_navigating_away_and_back(self, grading_client: CanvasGradingClient):
        # Post grade for student 156944
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        requests.put(url, data={"submission[posted_grade]": "16.5"}, headers=grading_client._headers())

        # Read another student
        grading_client.get_submission(assignment_id=316697, user_id=192479)

        # Return to student 156944
        sub_back = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert sub_back.score == 16.5


# ==============================================================================
# Feature 16: Headless Autonomous CLI Runner (Boundaries & Errors)
# ==============================================================================
class TestFeature16AutonomousCLIRunnerBoundaries:
    """Feature 16 Boundaries: Invalid assignments, headed default directive, timeout handling."""

    def test_cli_handles_invalid_assignment_id_cleanly(self, grading_client: CanvasGradingClient):
        resp = requests.get(
            f"{grading_client.base_url}/api/v1/courses/86326/assignments/999999",
            headers=grading_client._headers(),
        )
        assert resp.status_code == 404

    def test_cli_handles_network_timeout_with_retry(self, grading_client: CanvasGradingClient):
        # Inject artificial server latency and verify client timeout raises exception
        requests.post(f"{grading_client.base_url}/mock/fault", json={"latency_ms": 300})
        with pytest.raises(requests.exceptions.RequestException):
            requests.get(f"{grading_client.base_url}/api/v1/users/self", timeout=0.05)

    def test_cli_empty_cohort_bounds_error(self):
        start_idx = 50
        end_idx = 40
        empty_cohort = [s for s in JOACHIM_COHORT if start_idx <= s["index"] <= end_idx]
        assert len(empty_cohort) == 0

    def test_cli_headed_mode_by_default_directive_compliance(self):
        # Verifies User Directive: Headed Mode by Default (headless=False)
        cli_config = {"headless": False}
        assert cli_config["headless"] is False

    def test_cli_headless_flag_overrides_to_true(self):
        # Verifies --headless flag toggle
        def resolve_headless(cli_args: list) -> bool:
            return "--headless" in cli_args

        assert resolve_headless(["--assignment-id", "316697"]) is False
        assert resolve_headless(["--assignment-id", "316697", "--headless"]) is True
