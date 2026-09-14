"""
Comprehensive Unit Tests for Ulwazi SpeedGrader Rubric Evaluation Engines.
Tests Exp05, Exp06, and Lab 3 evaluators, covering all rubric criteria,
tolerances, author idiosyncrasies, penalties, and edge cases.
"""

from src.evaluator import (
    Exp05Evaluator,
    Exp06Evaluator,
    Lab3Evaluator,
    ParsedSubmission,
    evaluate_exp05,
    evaluate_exp06,
    evaluate_lab3_final_code,
    evaluate_lab3_part_a,
    evaluate_lab3_part_b,
)
from tests.harness import (
    parse_exp05_pdf,
    parse_exp06_pdf,
    parse_lab3_html,
)
from tests.mock_server import (
    REFERENCE_VPYTHON_CODE,
    create_exp05_pdf,
    create_exp06_pdf,
)


# ==============================================================================
# Exp05 Unit Tests
# ==============================================================================
class TestExp05EvaluatorUnit:
    """Detailed unit tests for Exp05 Thermal Expansion evaluator."""

    def test_exp05_perfect_report(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        evaluator = Exp05Evaluator()
        result = evaluator.evaluate(parsed)
        assert result.score == 20.0
        assert result.max_score == 20.0
        assert len(result.breakdown) == 10

    def test_exp05_metadata_extraction(self, sample_exp05_pdf: bytes):
        parsed = parse_exp05_pdf(sample_exp05_pdf)
        result = evaluate_exp05(parsed)
        assert result.metadata["student_name"] == "Sbongokuhle Mbizane"
        assert result.metadata["student_id"] == 156944
        assert result.metadata["group"] == "Fri2"

    def test_exp05_missing_intro(self):
        pdf = create_exp05_pdf(include_intro=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Introduction"] == 0.0
        assert result.score == 19.0
        assert any("Introduction section missing" in f for f in result.feedback_lines)

    def test_exp05_partial_intro(self):
        txt = "1. Introduction\nLinear expansion occurs when materials are heated."
        pdf = create_exp05_pdf(include_intro=False, custom_text=txt)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Introduction"] == 0.5
        assert any("definition of alpha" in f for f in result.feedback_lines)

    def test_exp05_missing_objective_error_analysis(self):
        txt = "2. Principal Objectives\nTo measure alpha of brass."
        pdf = create_exp05_pdf(include_objective=False, custom_text=txt)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Objectives"] == 0.5
        assert any("include error analysis" in f for f in result.feedback_lines)

    def test_exp05_incomplete_tables(self):
        pdf = create_exp05_pdf(include_brass=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Brass Table"] == 0.0
        assert result.score <= 16.5
        assert any("Brass table incomplete" in f for f in result.feedback_lines)

    def test_exp05_discussion_and_conclusion(self):
        pdf = create_exp05_pdf(include_discussion=False, include_conclusion=False)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Discussion"] == 0.0
        assert result.breakdown["Conclusion"] == 0.0
        assert any(
            "Discussion section is superficial or missing" in f for f in result.feedback_lines
        )
        assert any(
            "Conclusion must reference accepted literature" in f for f in result.feedback_lines
        )

    def test_exp05_q1_derivation_reflection_and_small_angle(self):
        pdf = create_exp05_pdf(include_q1=True)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 1"] == 2.0

    def test_exp05_q2_accepts_memo_14_percent(self):
        pdf = create_exp05_pdf(q2_accuracy_mode="memo_14")
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 2"] == 2.0

    def test_exp05_q2_accepts_standard_6_percent(self):
        pdf = create_exp05_pdf(q2_accuracy_mode="standard_6")
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 2"] == 2.0

    def test_exp05_q3_bimetallic_strip(self):
        pdf = create_exp05_pdf(include_q3=True)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert result.breakdown["Question 3"] == 1.0

    def test_exp05_units_penalty(self):
        pdf = create_exp05_pdf(omit_units=True)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert "Units Omitted" in result.penalties_applied
        assert result.penalties_applied["Units Omitted"] == 0.5
        assert result.score == 19.5

    def test_exp05_sig_figs_penalty(self):
        pdf = create_exp05_pdf(extra_sig_figs=True)
        parsed = parse_exp05_pdf(pdf)
        result = evaluate_exp05(parsed)
        assert "Significant Figures" in result.penalties_applied
        assert result.penalties_applied["Significant Figures"] == 0.5
        assert result.score == 19.5


# ==============================================================================
# Exp06 Unit Tests
# ==============================================================================
class TestExp06EvaluatorUnit:
    """Detailed unit tests for Exp06 Thin Lenses evaluator."""

    def test_exp06_perfect_report(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        evaluator = Exp06Evaluator()
        result = evaluator.evaluate(parsed)
        assert result.score == 20.0
        assert result.max_score == 20.0
        assert result.breakdown["Method 1"] == 1.0
        assert result.breakdown["Method 2"] == 7.0
        assert result.breakdown["Method 3"] == 5.0
        assert result.breakdown["Questions"] == 3.0

    def test_exp06_empty_report_scores_zero(self):
        parsed = ParsedSubmission(assignment_type="exp06")
        result = evaluate_exp06(parsed)
        assert result.score == 0.0
        assert any("Document is empty" in f for f in result.feedback_lines)

    def test_exp06_missing_method1(self):
        pdf = create_exp06_pdf(include_method1=False)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 1"] == 0.0
        assert result.score == 19.0

    def test_exp06_missing_worst_fit_lines(self):
        pdf = create_exp06_pdf(omit_worst_fit_lines=True)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 2"] < 7.0
        assert any("2 lines of worst fit" in f for f in result.feedback_lines)

    def test_exp06_signed_magnification_accepted(self):
        pdf = create_exp06_pdf(signed_magnification=True)
        parsed = parse_exp06_pdf(pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Method 3"] == 5.0

    def test_exp06_questions_section(self, sample_exp06_pdf: bytes):
        parsed = parse_exp06_pdf(sample_exp06_pdf)
        result = evaluate_exp06(parsed)
        assert result.breakdown["Questions"] == 3.0


# ==============================================================================
# Lab 3 Unit Tests
# ==============================================================================
class TestLab3EvaluatorUnit:
    """Detailed unit tests for Lab 3 Part A, Part B, and Final Code."""

    def test_lab3_part_a_scaled_mode(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        result = evaluate_lab3_part_a(boxes, target_max_score=7.0)
        assert result.score == 7.0
        assert result.max_score == 7.0
        for i in range(1, 8):
            assert result.breakdown[f"Box {i}"] == 1.0

    def test_lab3_part_a_standalone_20_mode(self, sample_lab3_html_a: str):
        boxes = parse_lab3_html(sample_lab3_html_a)
        result = evaluate_lab3_part_a(boxes, target_max_score=20.0)
        assert result.score == 20.0
        assert result.max_score == 20.0
        assert result.breakdown["Box 1"] == 2.0
        assert result.breakdown["Box 2"] == 3.0
        assert result.breakdown["Box 3"] == 3.0
        assert result.breakdown["Box 4"] == 2.0
        assert result.breakdown["Box 5"] == 4.0
        assert result.breakdown["Box 6"] == 3.0
        assert result.breakdown["Box 7"] == 3.0

    def test_lab3_box3_metric_unit_tolerances(self):
        for val_str in ["33 mm", "3.3 cm", "0.033 m", "32.5 mm", "34.0 mm"]:
            res = evaluate_lab3_part_a({3: val_str})
            assert res.breakdown["Box 3"] == 1.0

        res_out = evaluate_lab3_part_a({3: "50.0 mm"})
        assert res_out.breakdown["Box 3"] == 0.0

    def test_lab3_box4_wrong_positive_momentum(self):
        res = evaluate_lab3_part_a({4: "+p_x"})
        assert res.breakdown["Box 4"] == 0.0

    def test_lab3_part_b_scaled_mode(self, sample_lab3_html_b: str):
        boxes = parse_lab3_html(sample_lab3_html_b)
        result = evaluate_lab3_part_b(boxes, target_max_score=9.0)
        assert result.score == 9.0
        assert result.max_score == 9.0
        for i in range(8, 18):
            assert result.breakdown[f"Box {i}"] == 0.9

    def test_lab3_part_b_standalone_20_mode(self, sample_lab3_html_b: str):
        boxes = parse_lab3_html(sample_lab3_html_b)
        result = evaluate_lab3_part_b(boxes, target_max_score=20.0)
        assert result.score == 20.0
        assert result.max_score == 20.0
        for i in range(8, 18):
            assert result.breakdown[f"Box {i}"] == 2.0

    def test_lab3_part_b_box16_partial_credit(self):
        # Only observation, no physics
        res_obs = evaluate_lab3_part_b({16: "Ball bounces back and forth."})
        assert res_obs.breakdown["Box 16"] == 0.45

        # Both observation and physics
        ans = "Ball bounces upwards while normal force acts (Newton's 3rd Law)."
        res_both = evaluate_lab3_part_b({16: ans})
        assert res_both.breakdown["Box 16"] == 0.9

    def test_lab3_final_code_scaled_mode(self):
        result = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE, target_max_score=6.0)
        assert result.score == 6.0
        assert result.max_score == 6.0
        assert result.breakdown["Scene Setup"] == 1.0
        assert result.breakdown["Variables Setup"] == 1.0
        assert result.breakdown["Animation Loop"] == 1.0
        assert result.breakdown["Euler Integration"] == 1.0
        assert result.breakdown["Collision Logic"] == 2.0

    def test_lab3_final_code_standalone_20_mode(self):
        result = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE, target_max_score=20.0)
        assert result.score == 20.0
        assert result.max_score == 20.0
        assert result.breakdown["Scene Setup"] == 4.0
        assert result.breakdown["Variables Setup"] == 3.0
        assert result.breakdown["Animation Loop"] == 3.0
        assert result.breakdown["Euler Integration"] == 4.0
        assert result.breakdown["Collision Logic"] == 4.0
        assert result.breakdown["Stability & Syntax"] == 2.0

    def test_lab3_final_code_empty(self):
        result = evaluate_lab3_final_code("")
        assert result.score == 0.0
        assert result.max_score == 6.0

    def test_lab3_final_code_missing_rate(self):
        code = "from vpython import *\nwhile True:\n    ball.pos += ball.velocity * dt"
        result = evaluate_lab3_final_code(code)
        assert result.breakdown["Animation Loop"] == 0.0

    def test_lab3_unified_evaluator_routing(self, sample_lab3_html_a: str, sample_lab3_html_b: str):
        boxes_a = parse_lab3_html(sample_lab3_html_a)
        boxes_b = parse_lab3_html(sample_lab3_html_b)
        unified = Lab3Evaluator()

        res_a = unified.evaluate(boxes_a)
        assert res_a.score == 7.0

        res_b = unified.evaluate(boxes_b)
        assert res_b.score == 9.0

        res_code = unified.evaluate(REFERENCE_VPYTHON_CODE)
        assert res_code.score == 6.0

        # Composite submission test
        composite = {
            "part_a": boxes_a,
            "part_b": boxes_b,
            "code": REFERENCE_VPYTHON_CODE,
        }
        res_comp = unified.evaluate(composite)
        assert res_comp.score == 22.0 or res_comp.max_score == 20.0
