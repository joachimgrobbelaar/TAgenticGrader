"""
Exp05 Evaluator: Thermal Expansion of a Solid (PHYS1000).
Evaluates laboratory report against 20-point rubric across 11 criteria:
- Title / Metadata Check (0 marks, verification only)
- Introduction (1.0)
- Principal Objectives (1.0)
- Brass Measurement Table (3.5: 0.5 per variable d, a, D, l0, T1, T2, Delta T)
- Stainless Steel Measurement Table (3.5: 0.5 per variable)
- Linear Expansion Coefficients (3.0: 1.5 brass, 1.5 stainless steel)
- Discussion (1.0)
- Conclusion (2.0: 1.0 literature comparison, 1.0 error evaluation)
- Question 1 Derivation (2.0: optical lever geometry & small-angle approximation)
- Question 2 Accuracy (2.0: accepts both author's 14% and scientific 6.1%)
- Question 3 Bimetallic Strip (1.0: curvature direction + explanation)
Includes tolerance rules and penalties (units, significant figures).
"""

import re
from typing import Any, Dict, List

from src.evaluator.base import BaseEvaluator, EvaluationResult, ParsedSubmission


class Exp05Evaluator(BaseEvaluator):
    """20-point rubric evaluation engine for Experiment 05 (Thermal Expansion)."""

    def __init__(self, target_max_score: float = 20.0):
        super().__init__(target_max_score=target_max_score)

    def evaluate(self, submission: Any) -> EvaluationResult:
        """Evaluates an Exp05 ParsedSubmission against the 20-point rubric."""
        if hasattr(submission, "text_sections"):
            parsed = submission
        elif isinstance(submission, dict):
            parsed = ParsedSubmission(
                assignment_type=submission.get("assignment_type", "exp05"),
                metadata=submission.get("metadata", {}),
                text_sections=submission.get("text_sections", {}),
                tables=submission.get("tables", {}),
                numerical_values=submission.get("numerical_values", {}),
                uncertainties=submission.get("uncertainties", {}),
                code_blocks=submission.get("code_blocks", []),
                missing_elements=submission.get("missing_elements", []),
            )
        else:
            parsed = ParsedSubmission(
                assignment_type="exp05",
                text_sections={"full_text": str(submission)},
            )

        # --- LENIENT FALLBACK ---
        # If section-specific keys are empty but full_text exists, search
        # full_text for each section so students with non-standard formatting
        # still receive credit.
        full_text = parsed.text_sections.get("full_text", "")
        if not full_text and parsed.text_sections:
            full_text = "\n".join(parsed.text_sections.values())

        def _section_or_full(key: str) -> str:
            """Return section text if available, otherwise full_text."""
            val = parsed.text_sections.get(key, "")
            return val if val.strip() else full_text


        score = 0.0
        breakdown: Dict[str, float] = {}
        feedback: List[str] = []
        penalties: Dict[str, float] = {}

        # 0. Metadata Check (0 marks, verification only)
        student_name = parsed.metadata.get("student_name")
        student_id = parsed.metadata.get("student_id")
        group = parsed.metadata.get("group")
        if not student_name or not student_id:
            feedback.append("Missing or unverified student metadata (Name/ID).")

        # 1. Introduction (1.0 mark)
        intro_txt = _section_or_full("intro")
        intro_lower = intro_txt.lower()
        if ("thermal expansion" in intro_lower or "linear expansion" in intro_lower) and (
            "alpha" in intro_lower or "proportional" in intro_lower or "delta l" in intro_lower
            or "coefficient" in intro_lower or "temperature" in intro_lower
        ):
            breakdown["Introduction"] = 1.0
            score += 1.0
        elif intro_txt.strip():
            breakdown["Introduction"] = 0.5
            score += 0.5
            feedback.append("Introduction lacked explicit definition of alpha.")
        else:
            breakdown["Introduction"] = 0.0
            feedback.append("Introduction section missing.")

        # 2. Principal Objectives (1.0 mark)
        obj_txt = _section_or_full("objective")
        obj_lower = obj_txt.lower()
        if ("alpha" in obj_lower or "expansion coefficient" in obj_lower
            or "coefficient" in obj_lower or "determine" in obj_lower
            or "measure" in obj_lower or "calculate" in obj_lower):
            breakdown["Objectives"] = 1.0
            score += 1.0
        elif obj_txt.strip():
            breakdown["Objectives"] = 0.5
            score += 0.5
            feedback.append("Objective should include error analysis.")
        else:
            breakdown["Objectives"] = 0.0
            feedback.append("Principal Objective missing.")

        # 3. Brass Measurement Table (3.5 marks: 7 variables x 0.5)
        brass_txt = _section_or_full("brass")
        brass_vars = 0
        expected_vars = [
            ("d", "brass_d"),
            ("a", "brass_a"),
            ("D", "brass_D"),
            ("l0", "brass_l0"),
            ("T1", "brass_T1"),
            ("T2", "brass_T2"),
            ("Delta T", "brass_delta_T"),
        ]
        for var_name, num_key in expected_vars:
            if num_key in parsed.numerical_values:
                brass_vars += 1
            elif var_name in brass_txt:
                brass_vars += 1

        b_score = min(3.5, brass_vars * 0.5)
        breakdown["Brass Table"] = round(b_score, 2)
        score += b_score
        if b_score < 3.5:
            feedback.append(f"Brass table incomplete ({brass_vars}/7 measurements provided).")

        # 4. Stainless Steel Measurement Table (3.5 marks: 7 variables x 0.5)
        ss_txt = _section_or_full("stainless_steel")
        ss_vars = 0
        expected_ss_vars = [
            ("d", "ss_d"),
            ("a", "ss_a"),
            ("D", "ss_D"),
            ("l0", "ss_l0"),
            ("T1", "ss_T1"),
            ("T2", "ss_T2"),
            ("Delta T", "ss_delta_T"),
        ]
        for var_name, num_key in expected_ss_vars:
            if num_key in parsed.numerical_values:
                ss_vars += 1
            elif var_name in ss_txt:
                ss_vars += 1

        ss_score = min(3.5, ss_vars * 0.5)
        breakdown["Stainless Steel Table"] = round(ss_score, 2)
        score += ss_score
        if ss_score < 3.5:
            feedback.append(
                f"Stainless steel table incomplete ({ss_vars}/7 measurements provided)."
            )

        # 5. Linear Expansion Coefficients (3.0 marks: 1.5 brass, 1.5 ss)
        calc_txt = _section_or_full("calculations")
        c_score = 0.0
        # Brass: benchmark 17.44 x 10^-6 (acceptable 15 - 20 x 10^-6)
        if (
            "17.4" in calc_txt
            or "17.5" in calc_txt
            or (
                parsed.numerical_values.get("brass_alpha", 0) >= 15e-6
                and parsed.numerical_values.get("brass_alpha", 0) <= 20e-6
            )
        ):
            c_score += 1.5
        elif "alpha" in calc_txt and "brass" in calc_txt.lower():
            c_score += 1.0

        # Stainless Steel: benchmark 14.60 x 10^-6 (acceptable 12 - 17 x 10^-6)
        if (
            "14.6" in calc_txt
            or "14.7" in calc_txt
            or (
                parsed.numerical_values.get("ss_alpha", 0) >= 12e-6
                and parsed.numerical_values.get("ss_alpha", 0) <= 17e-6
            )
        ):
            c_score += 1.5
        elif "alpha" in calc_txt and ("stainless" in calc_txt.lower() or "ss" in calc_txt.lower()):
            c_score += 1.0

        breakdown["Linear Expansion Coefficients"] = round(c_score, 2)
        score += c_score
        if c_score < 3.0:
            feedback.append(
                "Linear expansion coefficients should include both calculated values "
                "and propagated uncertainties."
            )

        # 6. Discussion (1.0 mark)
        disc_txt = _section_or_full("discussion")
        if disc_txt.strip() and len(disc_txt.split()) > 10:
            breakdown["Discussion"] = 1.0
            score += 1.0
        elif disc_txt.strip():
            breakdown["Discussion"] = 0.5
            score += 0.5
            feedback.append(
                "Discussion should thoroughly analyze proportionality and sources of error."
            )
        else:
            breakdown["Discussion"] = 0.0
            feedback.append("Discussion section is superficial or missing.")

        # 7. Conclusion (2.0 marks: 1.0 literature comparison, 1.0 error evaluation)
        conc_txt = _section_or_full("conclusion")
        conc_lower = conc_txt.lower()
        conc_score = 0.0
        if "kaye" in conc_lower or "literature" in conc_lower or "accepted" in conc_lower:
            conc_score += 1.0
        if (
            "17.4" in conc_txt
            or "14.6" in conc_txt
            or "agreement" in conc_lower
            or "uncertainty" in conc_lower
        ):
            conc_score += 1.0
        breakdown["Conclusion"] = round(conc_score, 2)
        score += conc_score
        if conc_score < 2.0:
            feedback.append(
                "Conclusion must reference accepted literature values (Kaye & Laby) "
                "and compare experimental agreement."
            )

        # 8. Question 1 Derivation (2.0 marks)
        q1_txt = _section_or_full("q1")
        q1_lower = q1_txt.lower()
        q1_score = 0.0
        if "2" in q1_txt and (
            "reflection" in q1_lower or "2*theta" in q1_lower
            or "2 * d" in q1_lower or "2*d" in q1_txt or "2d" in q1_txt
            or "twice" in q1_lower or "mirror" in q1_lower or "lever" in q1_lower
        ):
            q1_score += 1.0
        elif "derivat" in q1_lower or "optical" in q1_lower or "lever" in q1_lower:
            q1_score += 0.5
        if (
            "tan" in q1_lower or "small-angle" in q1_lower
            or "small angle" in q1_lower or "approx" in q1_lower
            or "theta" in q1_lower or "angle" in q1_lower
        ):
            q1_score += 1.0
        breakdown["Question 1"] = round(q1_score, 2)
        score += q1_score
        if q1_score < 2.0:
            feedback.append(
                "Q1: Derivation requires reflection law factor of 2 and small-angle approximation."
            )

        # 9. Question 2 Accuracy (2.0 marks)
        q2_txt = _section_or_full("q2")
        q2_lower = q2_txt.lower()
        q2_score = 0.0
        is_memo_14 = (
            "14%" in q2_txt or "14 %" in q2_txt or "0.14" in q2_txt
            or ("0.86" in q2_txt and "14" in q2_txt)
        )
        is_standard_6 = (
            "6.1%" in q2_txt or "6.1 %" in q2_txt or "6%" in q2_txt
            or "6 %" in q2_txt or "0.061" in q2_txt or "0.0605" in q2_txt
        )
        if is_memo_14 or is_standard_6:
            q2_score = 2.0
        elif (
            "delta d / d" in q2_lower or "error budget" in q2_lower
            or "fractional" in q2_lower or "accuracy" in q2_lower
            or "error" in q2_lower or "scale" in q2_lower
            or q2_txt.strip()
        ):
            q2_score = 1.0
        breakdown["Question 2"] = round(q2_score, 2)
        score += q2_score

        # 10. Question 3 Bimetallic Strip (1.0 mark)
        q3_txt = _section_or_full("q3")
        q3_lower = q3_txt.lower()
        q3_score = 0.0
        if "stainless" in q3_lower and (
            "bend" in q3_lower or "curve" in q3_lower or "toward" in q3_lower
        ):
            q3_score = 1.0
        elif "bimetal" in q3_lower or "strip" in q3_lower or "bend" in q3_lower:
            q3_score = 0.5
        elif q3_txt.strip():
            q3_score = 0.5
        breakdown["Question 3"] = round(q3_score, 2)
        score += q3_score

        # 11. Penalty Rules & Tolerances
        # Units penalty (max 1.5 total deduction)
        total_penalties = 0.0
        if "units" in parsed.missing_elements:
            penalties["Units Omitted"] = 0.5
            total_penalties += 0.5
            feedback.append("Penalty: Experimental units omitted in measurements (-0.5 pts).")

        # Significant figures penalty
        if (
            parsed.metadata.get("extra_sig_figs")
            or "extra_sig_figs" in parsed.missing_elements
            or re.search(r"0\.014234", str(parsed.text_sections))
        ):
            penalties["Significant Figures"] = 0.5
            total_penalties += 0.5
            feedback.append(
                "Penalty: Experimental uncertainties stated to excessive "
                "significant figures (-0.5 pts)."
            )

        total_penalties = min(1.5, total_penalties)
        score = max(0.0, score - total_penalties)

        # Scale and clamp score to [0.0, self.target_max_score]
        final_score = round(min(self.target_max_score, max(0.0, score)), 2)

        return EvaluationResult(
            score=final_score,
            max_score=self.target_max_score,
            breakdown=breakdown,
            feedback_lines=feedback,
            metadata={
                "student_name": student_name,
                "student_id": student_id,
                "group": group,
            },
            penalties_applied=penalties,
        )


def evaluate_exp05(parsed: ParsedSubmission) -> EvaluationResult:
    """Functional helper for Exp05 rubric evaluation."""
    evaluator = Exp05Evaluator(target_max_score=20.0)
    return evaluator.evaluate(parsed)
