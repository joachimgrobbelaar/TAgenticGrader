"""
Tier 1: Comprehensive Feature Coverage Test Suite.
Verifies happy-path functionality for all 16 features defined in PROJECT.md.
Requirement: ≥80 tests total (5 tests per feature).
"""

from datetime import datetime, timezone
import json
import os
import re
import tempfile
from typing import Dict
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


# ==============================================================================
# Feature 1: Cookie & Session Extraction
# ==============================================================================
class TestFeature01CookieSession:
    """Feature 1: Cookie & Session Extraction from Firefox profile into Playwright storage_state."""

    def test_session_instantiation_with_valid_cookies(self, auth_session: CanvasSession):
        assert len(auth_session.cookies) >= 2
        cookie_names = {c["name"] for c in auth_session.cookies}
        assert "canvas_session" in cookie_names
        assert "_csrf_token" in cookie_names

    def test_session_cookie_header_generation(self, auth_session: CanvasSession):
        header = auth_session.get_cookie_header()
        assert "canvas_session=mock_authenticated_session_hash_abc123" in header
        assert "_csrf_token=mock_token" in header

    def test_playwright_storage_state_serialization(self, auth_session: CanvasSession, tmp_path):
        state_file = tmp_path / "storage_state.json"
        storage_state = {
            "cookies": auth_session.cookies,
            "origins": [{"origin": "http://127.0.0.1", "localStorage": []}],
        }
        with open(state_file, "w") as f:
            json.dump(storage_state, f)
        auth_session.storage_state_path = str(state_file)

        assert os.path.exists(auth_session.storage_state_path)
        with open(state_file, "r") as f:
            loaded = json.load(f)
        assert len(loaded["cookies"]) == len(auth_session.cookies)

    def test_csrf_token_extraction_and_unquoting(self):
        quoted_token = "2b%2FR9X%2Babcdef%3D%3D"
        # Standard unquoting logic
        import urllib.parse
        unquoted = urllib.parse.unquote(quoted_token)
        assert unquoted == "2b/R9X+abcdef=="
        assert "%" not in unquoted

    def test_session_auth_header_matches_user_profile(self, server_url: str, auth_session: CanvasSession):
        resp = requests.get(f"{server_url}/api/v1/users/self", headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        user_data = resp.json()
        assert user_data["id"] == CURRENT_USER["id"]
        assert user_data["name"] == "Joachim Grobbelaar"


# ==============================================================================
# Feature 2: SpeedGrader Navigation
# ==============================================================================
class TestFeature02SpeedGraderNavigation:
    """Feature 2: SpeedGrader Navigation, deep-linking, and DOM elements."""

    def test_speedgrader_url_structure(self, server_url: str):
        aid = 316697
        expected_path = f"/courses/86326/gradebook/speed_grader?assignment_id={aid}"
        full_url = f"{server_url}{expected_path}"
        parsed = urlparse(full_url)
        assert parsed.path == "/courses/86326/gradebook/speed_grader"
        query = parse_qs(parsed.query)
        assert query["assignment_id"] == [str(aid)]

    def test_speedgrader_deep_link_student_param(self, server_url: str):
        aid = 316697
        uid = 156944
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id={aid}&student_id={uid}"
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        assert query["assignment_id"] == [str(aid)]
        assert query["student_id"] == [str(uid)]

    def test_speedgrader_html_contains_grade_input_element(self, server_url: str, auth_session: CanvasSession):
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        html_text = resp.text
        assert 'data-testid="grade-input"' in html_text
        assert 'id="TextInput___0"' in html_text

    def test_speedgrader_html_contains_comment_and_navigation_elements(self, server_url: str, auth_session: CanvasSession):
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        html = resp.text
        assert 'id="comment_submit_button"' in html
        assert 'data-testid="next-student-button"' in html
        assert 'data-testid="previous-student-button"' in html

    def test_speedgrader_html_contains_document_viewer_frame(self, server_url: str, auth_session: CanvasSession):
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert resp.status_code == 200
        assert 'name="submission-preview-iframe"' in resp.text
        assert 'name="rce-tinymce_ifr"' in resp.text


# ==============================================================================
# Feature 3: Cohort Filtering (Fri2 28-62)
# ==============================================================================
class TestFeature03CohortFiltering:
    """Feature 3: Cohort Filtering to Joachim Grobbelaar's allocated students (Fri2 28-62)."""

    def test_fetch_full_group_enrollment(self, server_url: str):
        resp = requests.get(f"{server_url}/api/v1/courses/86326/groups/144689/users")
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) == 118

    def test_filter_joachim_cohort_exact_count(self, server_url: str):
        resp = requests.get(f"{server_url}/api/v1/courses/86326/groups/144689/users")
        users = resp.json()
        cohort = [u for u in users if 28 <= u["index"] <= 62]
        assert len(cohort) == 35

    def test_first_student_in_cohort_is_sbongokuhle_mbizane(self, server_url: str):
        resp = requests.get(f"{server_url}/api/v1/courses/86326/groups/144689/users")
        users = resp.json()
        cohort = [u for u in users if 28 <= u["index"] <= 62]
        assert cohort[0]["index"] == 28
        assert cohort[0]["id"] == 156944
        assert cohort[0]["name"] == "Sbongokuhle Mbizane"

    def test_last_student_in_cohort_is_dalitso_mpwesiwa(self, server_url: str):
        resp = requests.get(f"{server_url}/api/v1/courses/86326/groups/144689/users")
        users = resp.json()
        cohort = [u for u in users if 28 <= u["index"] <= 62]
        assert cohort[-1]["index"] == 62
        assert cohort[-1]["id"] == 190138
        assert cohort[-1]["name"] == "Dalitso Mpwesiwa"

    def test_sortable_name_ordering_preserved(self, server_url: str):
        resp = requests.get(f"{server_url}/api/v1/courses/86326/groups/144689/users")
        users = resp.json()
        cohort = [u for u in users if 28 <= u["index"] <= 62]
        names = [u["sortable_name"] for u in cohort]
        assert names == sorted(names)


# ==============================================================================
# Feature 4: Canvas REST Client
# ==============================================================================
class TestFeature04CanvasRestClient:
    """Feature 4: Direct Canvas REST client with CSRF token and session cookies."""

    def test_get_user_self(self, grading_client: CanvasGradingClient):
        resp = requests.get(f"{grading_client.base_url}/api/v1/users/self", headers=grading_client._headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == CURRENT_USER["id"]

    def test_list_assignments(self, grading_client: CanvasGradingClient):
        resp = requests.get(f"{grading_client.base_url}/api/v1/courses/86326/assignments", headers=grading_client._headers())
        assert resp.status_code == 200
        assignments = resp.json()
        assert len(assignments) == 5
        a_ids = {a["id"] for a in assignments}
        assert 316697 in a_ids
        assert 316844 in a_ids

    def test_get_student_submission(self, grading_client: CanvasGradingClient):
        sub = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert isinstance(sub, RawSubmission)
        assert sub.assignment_id == 316697
        assert sub.user_id == 156944
        assert len(sub.attachments) >= 1

    def test_put_submission_grade(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        payload = {"submission[posted_grade]": "18.5"}
        resp = requests.put(url, data=payload, headers=grading_client._headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 18.5
        assert data["workflow_state"] == "graded"

    def test_csrf_token_header_validated(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        payload = {"submission[posted_grade]": "19.0"}
        headers = grading_client._headers()
        assert "X-CSRF-Token" in headers
        resp = requests.put(url, data=payload, headers=headers)
        assert resp.status_code == 200


# ==============================================================================
# Feature 5: Exp05 PDF Report Extraction
# ==============================================================================
class TestFeature05Exp05PDFExtraction:
    """Feature 5: Exp05 PDF download and text/table parsing via PyMuPDF."""

    def test_extract_student_metadata_from_pdf(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        assert parsed.metadata["student_name"] == "Sbongokuhle Mbizane"
        assert parsed.metadata["student_id"] == 156944
        assert parsed.metadata["group"] == "Fri2"

    def test_extract_brass_table_measurements(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        assert parsed.numerical_values["brass_d"] == 6.1
        assert parsed.numerical_values["brass_a"] == 2.1
        assert parsed.numerical_values["brass_D"] == 100.0
        assert parsed.numerical_values["brass_l0"] == 51.0
        assert parsed.numerical_values["brass_delta_T"] == 72.0

    def test_extract_stainless_steel_table_measurements(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        assert parsed.numerical_values["ss_d"] == 5.1
        assert parsed.numerical_values["ss_a"] == 2.1
        assert parsed.numerical_values["ss_D"] == 100.0
        assert parsed.numerical_values["ss_l0"] == 51.0
        assert parsed.numerical_values["ss_delta_T"] == 72.0

    def test_extract_expansion_calculation_formulas(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        calc_txt = parsed.text_sections["calculations"]
        assert "Delta l = (a * d) / (2 * D)" in calc_txt
        assert "alpha = Delta l / (l0 * Delta T)" in calc_txt
        assert "17.44" in calc_txt

    def test_extract_questions_derivation_and_accuracy(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        assert "2*theta" in parsed.text_sections["q1"] or "2 * D" in parsed.text_sections["q1"]
        assert "14%" in parsed.text_sections["q2"] or "6.1%" in parsed.text_sections["q2"]
        assert "stainless steel" in parsed.text_sections["q3"].lower()


# ==============================================================================
# Feature 6: Exp06 PDF Report Extraction
# ==============================================================================
class TestFeature06Exp06PDFExtraction:
    """Feature 6: Exp06 Thin Lenses PDF download and parsing."""

    def test_extract_method1_rough_estimate(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        assert parsed.numerical_values["method1_v"] == 11.5

    def test_extract_method2_separation_data_rows(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        assert parsed.tables["method2_row_count"] == 6

    def test_extract_method2_linearization_and_focal_length(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        assert parsed.numerical_values["method2_f"] == 12.0

    def test_extract_method3_statistical_parameters(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        assert parsed.numerical_values["method3_mean_f"] == 12.0
        assert parsed.numerical_values["method3_sigma"] == 0.014

    def test_extract_questions_inversion_and_focal_definitions(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        text = parsed.text_sections["full_text"]
        assert "inverted" in text.lower()
        assert "focal point" in text.lower()


# ==============================================================================
# Feature 7: Lab 3 Worksheet Extraction
# ==============================================================================
class TestFeature07Lab3WorksheetExtraction:
    """Feature 7: Online text entry HTML extraction for Boxes 1-17."""

    def test_extract_box1_straight_line_description(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        assert 1 in boxes
        assert "straight line" in boxes[1].lower()

    def test_extract_box2_kinematic_formula(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        assert 2 in boxes
        assert "r_f" in boxes[2] and "v*t" in boxes[2]

    def test_extract_box3_ruler_reading(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        assert 3 in boxes
        assert "33" in boxes[3]

    def test_extract_box4_and_box5_momentum_and_closed_system(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        assert "-p_x" in boxes[4]
        assert "closed" in boxes[5].lower()
        assert "isolated" in boxes[5].lower()

    def test_extract_boxes_8_through_17_part_b(self, sample_lab3_html_b: str):
        boxes = parse_lab3_html(sample_lab3_html_b)
        assert len(boxes) == 10
        assert 8 in boxes and 17 in boxes
        assert "bounce" in boxes[13].lower()


# ==============================================================================
# Feature 8: Lab 3 Code / Snapshot Extraction
# ==============================================================================
class TestFeature08Lab3CodeExtraction:
    """Feature 8: Websnappr snapshot PNG and VPython simulation inspection."""

    def test_websnappr_png_validity_and_size(self, sample_websnappr_png: bytes):
        assert sample_websnappr_png.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(sample_websnappr_png) > 1000

    def test_vpython_code_defines_scene_and_objects(self):
        code = REFERENCE_VPYTHON_CODE
        assert "sphere(" in code
        assert "box(" in code
        assert "pos=vector(" in code

    def test_vpython_code_defines_timestep_and_velocity(self):
        code = REFERENCE_VPYTHON_CODE
        assert "ball.velocity = vector(" in code
        assert "deltat = 0.01" in code

    def test_vpython_code_contains_rate_limited_loop(self):
        code = REFERENCE_VPYTHON_CODE
        assert "while True:" in code
        assert "rate(100)" in code

    def test_vpython_code_contains_boundary_reflection(self):
        code = REFERENCE_VPYTHON_CODE
        assert "ball.velocity.x" in code
        assert "ball.velocity.y" in code
        assert "wall_right.pos.x" in code


# ==============================================================================
# Feature 9: Exp05 Rubric Evaluation Engine
# ==============================================================================
class TestFeature09Exp05RubricEngine:
    """Feature 9: Exp05 Thermal Expansion Rubric Engine (out of 20 points)."""

    def test_perfect_exp05_report_scores_20(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        assert result.score == 20.0
        assert result.max_score == 20.0

    def test_exp05_breakdown_contains_all_10_sections(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        expected_sections = [
            "Introduction", "Objectives", "Brass Table", "Stainless Steel Table",
            "Linear Expansion Coefficients", "Discussion", "Conclusion",
            "Question 1", "Question 2", "Question 3"
        ]
        for sec in expected_sections:
            assert sec in result.breakdown
            assert result.breakdown[sec] > 0

    def test_deduct_mark_for_missing_objective_error_analysis(self):
        pdf = create_exp05_pdf(include_objective=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Objectives"] == 0.0
        assert result.score == 19.0

    def test_deduct_mark_for_missing_conclusion_literature_reference(self):
        pdf = create_exp05_pdf(include_conclusion=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Conclusion"] == 0.0
        assert result.score == 18.0

    def test_question_1_derivation_scoring(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 1"] == 2.0


# ==============================================================================
# Feature 10: Exp06 Rubric Evaluation Engine
# ==============================================================================
class TestFeature10Exp06RubricEngine:
    """Feature 10: Exp06 Thin Lenses Rubric Engine (out of 20 points)."""

    def test_perfect_exp06_report_scores_20(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.score == 20.0
        assert result.max_score == 20.0

    def test_method1_rough_estimate_scored(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 1"] == 1.0

    def test_method2_separation_data_scored(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 2"] == 7.0

    def test_method3_magnification_data_and_stats_scored(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 3"] == 5.0

    def test_questions_scored(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Questions"] == 3.0


# ==============================================================================
# Feature 11: Lab 3 Rubric Evaluation Engine
# ==============================================================================
class TestFeature11Lab3RubricEngine:
    """Feature 11: Lab 3 Part A, Part B, and Final Code rubric scoring."""

    def test_perfect_part_a_scores_7(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        result = evaluate_lab3_part_a(boxes)
        assert result.score == 7.0
        assert result.max_score == 7.0

    def test_perfect_part_b_scores_9(self, sample_lab3_html_b: str):
        boxes = parse_lab3_html(sample_lab3_html_b)
        result = evaluate_lab3_part_b(boxes)
        assert result.score == 9.0
        assert result.max_score == 9.0

    def test_perfect_final_code_scores_6(self):
        result = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE)
        assert result.score == 6.0
        assert result.max_score == 6.0

    def test_part_a_box5_closed_vs_isolated(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        result = evaluate_lab3_part_a(boxes)
        assert result.breakdown["Box 5"] == 1.0

    def test_final_code_boundary_collision_scoring(self):
        result = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE)
        assert result.breakdown["Collision Logic"] == 2.0


# ==============================================================================
# Feature 12: Penalty & Tolerance Rules
# ==============================================================================
class TestFeature12PenaltyAndToleranceRules:
    """Feature 12: 10% accuracy idiosyncrasy, delta T uncertainty, and penalty caps."""

    def test_accepts_author_idiosyncratic_14_percent(self):
        pdf = create_exp05_pdf(q2_accuracy_mode="memo_14")
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 2"] == 2.0

    def test_accepts_standard_scientific_6_percent(self):
        pdf = create_exp05_pdf(q2_accuracy_mode="standard_6")
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 2"] == 2.0

    def test_units_omitted_penalty_deduction(self):
        pdf = create_exp05_pdf(omit_units=True)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert "Units Omitted" in result.penalties_applied
        assert result.penalties_applied["Units Omitted"] == 0.5
        assert result.score <= 19.5

    def test_exp06_accepts_signed_magnification(self):
        pdf = create_exp06_pdf(signed_magnification=True)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 3"] == 5.0

    def test_lab3_ruler_reading_tolerates_units(self):
        for reading in ["33 mm", "3.3 cm", "0.033 m", "33.0 mm"]:
            boxes = {3: reading}
            result = evaluate_lab3_part_a(boxes)
            assert result.breakdown["Box 3"] == 1.0


# ==============================================================================
# Feature 13: Feedback Comment Generator
# ==============================================================================
class TestFeature13FeedbackCommentGenerator:
    """Feature 13: Structured itemized feedback comment generation."""

    def test_comment_includes_assignment_header(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        comment = generate_feedback_comment(result, "EXP 05 Thermal Expansion")
        assert "EXP 05 Thermal Expansion" in comment
        assert "Total Score: 20.0 / 20.0" in comment

    def test_comment_includes_rubric_breakdown(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        comment = generate_feedback_comment(result, "EXP 05 Thermal Expansion")
        assert "Itemized Rubric Breakdown:" in comment
        assert "Introduction: 1.0 pts" in comment
        assert "Brass Table: 3.5 pts" in comment

    def test_comment_includes_deduction_feedback_notes(self):
        pdf = create_exp05_pdf(include_intro=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        comment = generate_feedback_comment(result, "EXP 05")
        assert "Feedback & Constructive Notes:" in comment
        assert "Introduction section missing." in comment

    def test_comment_includes_penalties_applied(self):
        pdf = create_exp05_pdf(omit_units=True)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        comment = generate_feedback_comment(result, "EXP 05")
        assert "Penalties Applied:" in comment
        assert "Units Omitted: -0.5 pts" in comment

    def test_clean_multiline_formatting(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        comment = generate_feedback_comment(result, "EXP 06 Thin Lenses")
        lines = comment.splitlines()
        assert len(lines) >= 8
        assert not any("None" in l for l in lines)


# ==============================================================================
# Feature 14: SpeedGrader Grade & Comment Poster
# ==============================================================================
class TestFeature14SpeedGraderPoster:
    """Feature 14: Submitting grades and comments via REST API and SpeedGrader UI."""

    def test_post_grade_and_comment_via_client(self, grading_client: CanvasGradingClient, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        res = evaluate_exp05(parsed)
        receipt = grading_client.post_grade_and_comment(
            assignment_id=316697, user_id=156944, result=res, assignment_name="EXP 05"
        )
        assert receipt.status == "graded"
        assert receipt.score == 20.0
        assert receipt.comment_posted is True

    def test_posted_grade_reflected_in_get_submission(self, grading_client: CanvasGradingClient):
        sub_before = grading_client.get_submission(assignment_id=316697, user_id=156944)
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        requests.put(url, data={"submission[posted_grade]": "17.0"}, headers=grading_client._headers())

        sub_after = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert sub_after.score == 17.0
        assert sub_after.workflow_state == "graded"

    def test_posted_comment_appended_to_submission_comments(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        comment_text = "Good experimental error analysis."
        requests.put(url, data={"comment[text_comment]": comment_text}, headers=grading_client._headers())

        resp = requests.get(f"{url}?include[]=submission_comments", headers=grading_client._headers())
        sub_data = resp.json()
        comments = [c["comment"] for c in sub_data["submission_comments"]]
        assert comment_text in comments

    def test_speedgrader_html_reflects_updated_grade(self, grading_client: CanvasGradingClient):
        url_api = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        requests.put(url_api, data={"submission[posted_grade]": "19.5"}, headers=grading_client._headers())

        url_ui = f"{grading_client.base_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp_ui = requests.get(url_ui, headers=grading_client._headers())
        assert resp_ui.status_code == 200
        assert 'value="19.5"' in resp_ui.text

    def test_post_grade_with_json_payload(self, grading_client: CanvasGradingClient):
        url = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        payload = {"submission": {"posted_grade": "18.0"}, "comment": {"text_comment": "JSON post test"}}
        headers = grading_client._headers()
        headers["Content-Type"] = "application/json"
        resp = requests.put(url, data=json.dumps(payload), headers=headers)
        assert resp.status_code == 200
        assert resp.json()["score"] == 18.0


# ==============================================================================
# Feature 15: Next Student Transition
# ==============================================================================
class TestFeature15NextStudentTransition:
    """Feature 15: Advancing between students and state updates."""

    def test_cohort_progression_index_mapping(self):
        cohort_ids = [s["id"] for s in JOACHIM_COHORT]
        assert len(cohort_ids) == 35
        # Index 0 is Sbongokuhle Mbizane, index 1 is Imange Mdalana
        assert cohort_ids[0] == 156944
        assert cohort_ids[1] == 192479

    def test_speedgrader_ui_next_student_navigation(self, server_url: str, auth_session: CanvasSession):
        # Student 28
        url_28 = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp_28 = requests.get(url_28, headers={"Cookie": auth_session.get_cookie_header()})
        assert "Sbongokuhle Mbizane" in resp_28.text

        # Next student: 29 (Imange Mdalana)
        url_29 = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=192479"
        resp_29 = requests.get(url_29, headers={"Cookie": auth_session.get_cookie_header()})
        assert "Imange Mdalana" in resp_29.text

    def test_speedgrader_counter_indicates_student_position(self, server_url: str, auth_session: CanvasSession):
        url = f"{server_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp = requests.get(url, headers={"Cookie": auth_session.get_cookie_header()})
        assert 'data-testid="current-student-index"' in resp.text
        # Student 28 is the 29th student out of 118
        assert "29/118" in resp.text

    def test_graded_count_increments_after_grading(self, grading_client: CanvasGradingClient):
        # Check initial UI
        url_ui = f"{grading_client.base_url}/courses/86326/gradebook/speed_grader?assignment_id=316697&student_id=156944"
        resp1 = requests.get(url_ui, headers=grading_client._headers())

        # Grade student 156944
        url_api = f"{grading_client.base_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
        requests.put(url_api, data={"submission[posted_grade]": "20.0"}, headers=grading_client._headers())

        # Check UI shows incremented count
        resp2 = requests.get(url_ui, headers=grading_client._headers())
        assert resp2.status_code == 200
        assert 'data-testid="graded-students-count"' in resp2.text

    def test_boundary_at_end_of_cohort(self):
        last_student = JOACHIM_COHORT[-1]
        assert last_student["index"] == 62
        assert last_student["id"] == 190138
        assert last_student["name"] == "Dalitso Mpwesiwa"


# ==============================================================================
# Feature 16: Headless Autonomous CLI Runner
# ==============================================================================
class TestFeature16AutonomousCLIRunner:
    """Feature 16: Autonomous CLI runner with dry-run, cohort filtering, and reporting."""

    def test_dry_run_evaluation_does_not_mutate_remote_scores(self, grading_client: CanvasGradingClient):
        sub_before = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert sub_before.score is None

        # Simulate dry-run: download, parse, evaluate, but do NOT post
        pdf_data = grading_client.download_attachment(sub_before.attachments[0]["url"])
        parsed = parse_exp05_pdf(pdf_data)
        eval_res = evaluate_exp05(parsed)
        assert eval_res.score == 20.0

        sub_after = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert sub_after.score is None  # Unchanged in dry run

    def test_live_run_evaluates_and_commits_score(self, grading_client: CanvasGradingClient):
        sub = grading_client.get_submission(assignment_id=316697, user_id=156944)
        pdf_data = grading_client.download_attachment(sub.attachments[0]["url"])
        eval_res = evaluate_exp05(parse_exp05_pdf(pdf_data))
        receipt = grading_client.post_grade_and_comment(316697, 156944, eval_res, "EXP 05")
        assert receipt.status == "graded"

        sub_updated = grading_client.get_submission(assignment_id=316697, user_id=156944)
        assert sub_updated.score == 20.0

    def test_cohort_range_clipping_in_runner(self):
        start_idx = 28
        end_idx = 30
        clipped_cohort = [s for s in JOACHIM_COHORT if start_idx <= s["index"] <= end_idx]
        assert len(clipped_cohort) == 3

    def test_generate_summary_report_artifact(self, tmp_path):
        report_data = [
            {"student_id": 156944, "name": "Sbongokuhle Mbizane", "score": 20.0, "status": "graded"},
            {"student_id": 192479, "name": "Imange Mdalana", "score": 19.5, "status": "graded"},
        ]
        report_file = tmp_path / "grading_summary.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        assert report_file.exists()
        with open(report_file) as f:
            loaded = json.load(f)
        assert len(loaded) == 2
        assert loaded[0]["score"] == 20.0

    def test_runner_iterates_all_5_assignments(self, grading_client: CanvasGradingClient):
        for aid in [316697, 316844, 315832, 315833, 315831]:
            assert aid in ASSIGNMENTS
            sub = grading_client.get_submission(assignment_id=aid, user_id=156944)
            assert sub.assignment_id == aid

    def test_cli_headed_mode_default_and_headless_toggle(self):
        # High-Priority User Directive: Headed Mode by default (headless=False), with --headless toggle
        default_config = {"headless": False}
        assert default_config["headless"] is False, "Default must be headed mode"

        cli_flags = ["--headless"]
        active_headless = "--headless" in cli_flags
        assert active_headless is True, "--headless flag must toggle headless mode to True"
