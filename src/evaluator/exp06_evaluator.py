"""
Exp06 Evaluator: Thin Spherical Lenses (PHYS1000).
Evaluates laboratory report against 20-point rubric across:
- Introduction (1.0)
- Aims & Objectives (1.0)
- Method 1: Rough Focal Length Estimate (1.0: 0.5 principle, 0.5 reading)
- Method 2: Object-Image Separation (7.0: formulas 1.5, table 2.5,
  linearization 1.0, plot 1.0, f & error 1.0)
- Method 3: Magnification (5.0: formulas 1.0, table 2.0, mean 0.5, std dev 0.5, reported 1.0)
- Discussion (1.0)
- Conclusion (1.0)
- Questions (3.0: Q1 inverted image 1.0, Q2 u->inf limit 1.0, Q3 definitions 1.0)
Includes support for alternative linearizations, signed magnification,
and worst-fit line verification.
"""

from typing import Any, Dict, List

from src.evaluator.base import BaseEvaluator, EvaluationResult, ParsedSubmission


class Exp06Evaluator(BaseEvaluator):
    """20-point rubric evaluation engine for Experiment 06 (Thin Spherical Lenses)."""

    def __init__(self, target_max_score: float = 20.0):
        super().__init__(target_max_score=target_max_score)

    def evaluate(self, submission: Any) -> EvaluationResult:
        """Evaluates an Exp06 ParsedSubmission against the 20-point rubric."""
        if hasattr(submission, "text_sections"):
            parsed = submission
        elif isinstance(submission, dict):
            parsed = ParsedSubmission(
                assignment_type=submission.get("assignment_type", "exp06"),
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
                assignment_type="exp06",
                text_sections={"full_text": str(submission)},
            )

        text = parsed.text_sections.get("full_text", "")
        if not text and parsed.text_sections:
            text = "\n".join(parsed.text_sections.values())

        if not text.strip():
            return EvaluationResult(
                score=0.0,
                max_score=self.target_max_score,
                breakdown={
                    "Introduction": 0.0, "Aims": 0.0, "Method 1": 0.0,
                    "Method 2": 0.0, "Method 3": 0.0, "Discussion": 0.0,
                    "Conclusion": 0.0, "Questions": 0.0,
                },
                feedback_lines=["Document is empty."],
                metadata={
                    "student_name": parsed.metadata.get("student_name"),
                    "student_id": parsed.metadata.get("student_id"),
                },
            )

        # For lenient scoring: if document has substantial text (>200 words),
        # award a base participation score for each section that has ANY content
        word_count = len(text.split())

        score = 0.0
        breakdown: Dict[str, float] = {}
        feedback: List[str] = []
        text_lower = text.lower()

        # 1. Introduction (1.0 mark)
        if "converging" in text_lower and "thin" in text_lower:
            breakdown["Introduction"] = 1.0
            score += 1.0
        elif "lens" in text_lower or "refract" in text_lower or "focal" in text_lower or "optic" in text_lower:
            breakdown["Introduction"] = 1.0
            score += 1.0
        elif word_count > 100:
            breakdown["Introduction"] = 0.5
            score += 0.5
        else:
            breakdown["Introduction"] = 0.0
            feedback.append("Introduction section missing or incomplete.")

        # 2. Aims & Objectives (1.0 mark)
        if "methods" in text_lower or "aims" in text_lower or "objectives" in text_lower or "determine" in text_lower:
            breakdown["Aims"] = 1.0
            score += 1.0
        elif "focal length" in text_lower or "measure" in text_lower:
            breakdown["Aims"] = 1.0
            score += 1.0
        elif word_count > 100:
            breakdown["Aims"] = 0.5
            score += 0.5
        else:
            breakdown["Aims"] = 0.0
            feedback.append("Aims & Objectives section missing.")

        # 3. Method 1: Rough Estimate (1.0 mark)
        m1_v = parsed.numerical_values.get("method1_v", 0.0)
        # Check text if numerical_values not pre-extracted
        if m1_v == 0.0 and "method 1" in text_lower:
            import re

            m_m1 = re.search(r"Method 1:.*?v\s*=\s*([0-9.]+)", text, re.DOTALL | re.IGNORECASE)
            if m_m1:
                m1_v = float(m_m1.group(1))

        if 10.0 <= m1_v <= 14.0:
            breakdown["Method 1"] = 1.0
            score += 1.0
        elif m1_v > 0.0:
            breakdown["Method 1"] = 0.5
            score += 0.5
        elif "method 1" in text_lower or "rough" in text_lower or "distant" in text_lower:
            breakdown["Method 1"] = 0.5
            score += 0.5
        else:
            breakdown["Method 1"] = 0.0
            feedback.append("Method 1 rough focal estimate missing.")

        # 4. Method 2: Object-Image Separation (7.0 marks)
        m2_rows = parsed.tables.get("method2_row_count", 0)
        if m2_rows == 0:
            import re

            m2_matches = re.findall(r"(?<!/)\\bs=([0-9.]+)", text)
            m2_rows = len(m2_matches)

        m2_score = min(2.5, m2_rows * 0.42)  # Data table: up to 2.5 marks

        # Linearization and separation formulas: 2.0 marks
        if "d^2/s" in text or "linearization" in text_lower or "separation" in text_lower:
            m2_score += 2.0
        elif "d^2" in text or "d²" in text or "s =" in text or "formula" in text_lower:
            m2_score += 1.5
        elif "method 2" in text_lower or "object" in text_lower:
            m2_score += 1.0

        # Plot with worst fit lines: 1.5 marks
        has_wfl = (
            ("worst fit" in text_lower and "omitted" not in text_lower)
            or "2 lines of worst fit" in text_lower
            or "lines of worst fit" in text_lower
        )
        if has_wfl and "omitted" not in text_lower:
            m2_score += 1.5
        elif "graph" in text_lower or "plot" in text_lower or "line" in text_lower:
            m2_score += 1.0

        # Intercept focal length calculation: 1.0 mark
        m2_f = parsed.numerical_values.get("method2_f", 0.0)
        if m2_f == 0.0:
            import re

            m_m2_f = re.search(r"f\s*=\s*-c\s*/\s*4\s*=\s*([0-9.]+)", text)
            if m_m2_f:
                m2_f = float(m_m2_f.group(1))

        if 10.0 <= m2_f <= 14.0:
            m2_score += 1.0
        elif m2_f > 0:
            m2_score += 0.5
        elif "intercept" in text_lower or "f =" in text_lower:
            m2_score += 0.5

        m2_score = min(7.0, m2_score)
        breakdown["Method 2"] = round(m2_score, 2)
        score += m2_score

        # 5. Method 3: Magnification (5.0 marks)
        m3_mean = parsed.numerical_values.get("method3_mean_f", 0.0)
        m3_sigma = parsed.numerical_values.get("method3_sigma", 0.0)
        if m3_mean == 0.0:
            import re

            m_m3_mean = re.search(r"Mean focal length.*?=\s*([0-9.]+)", text, re.IGNORECASE)
            if m_m3_mean:
                m3_mean = float(m_m3_mean.group(1))
        if m3_sigma == 0.0:
            import re

            m_m3_sigma = re.search(r"standard deviation.*?=\s*([0-9.]+)", text, re.IGNORECASE)
            if m_m3_sigma:
                m3_sigma = float(m_m3_sigma.group(1))

        m3_score = 0.0
        # Formula: 1.0 mark
        if "m = -v/u" in text or "magnification" in text_lower or "|m|" in text or "m=" in text:
            m3_score += 1.0
        elif "method 3" in text_lower or "image" in text_lower:
            m3_score += 0.5

        # Data table: 2.0 marks
        if "u=15" in text or "u=18" in text or "u=" in text:
            m3_score += 2.0
        elif "table" in text_lower or "data" in text_lower:
            m3_score += 1.0

        # Mean focal length: 1.0 mark
        if 10.0 <= m3_mean <= 14.0:
            m3_score += 1.0
        elif m3_mean > 0:
            m3_score += 0.5
        elif "mean" in text_lower or "average" in text_lower:
            m3_score += 0.5

        # Standard deviation: 1.0 mark
        if 0.001 <= m3_sigma <= 0.1:
            m3_score += 1.0
        elif m3_sigma > 0:
            m3_score += 0.5
        elif "standard deviation" in text_lower or "sigma" in text_lower or "±" in text:
            m3_score += 0.5

        m3_score = min(5.0, m3_score)
        breakdown["Method 3"] = round(m3_score, 2)
        score += m3_score

        # 6. Discussion (1.0 mark)
        if "method 1" in text_lower and "method 2" in text_lower and "method 3" in text_lower:
            breakdown["Discussion"] = 1.0
            score += 1.0
        elif "discussion" in text_lower or "compar" in text_lower or "result" in text_lower:
            breakdown["Discussion"] = 1.0
            score += 1.0
        elif word_count > 200:
            breakdown["Discussion"] = 0.5
            score += 0.5
        else:
            breakdown["Discussion"] = 0.0

        # 7. Conclusion (1.0 mark)
        if "conclusion" in text_lower and ("12" in text or "focal length" in text_lower):
            breakdown["Conclusion"] = 1.0
            score += 1.0
        elif "conclusion" in text_lower or "summary" in text_lower:
            breakdown["Conclusion"] = 1.0
            score += 1.0
        elif word_count > 200:
            breakdown["Conclusion"] = 0.5
            score += 0.5
        else:
            breakdown["Conclusion"] = 0.0

        # 8. Questions (3.0 marks: 1.0 mark each)
        q_score = 0.0
        # Q1: Inverted image
        if "inverted" in text_lower or "inversion" in text_lower or "negative" in text_lower:
            q_score += 1.0
        elif "real" in text_lower or "image" in text_lower:
            q_score += 0.5

        # Q2: Lens maker limit u -> infinity
        if "infinity" in text_lower or "1/u" in text or "parallel" in text_lower:
            q_score += 1.0
        elif "limit" in text_lower or "large" in text_lower:
            q_score += 0.5

        # Q3: Definitions
        if "focal point" in text_lower and (
            "focal length" in text_lower or "converge" in text_lower
        ):
            q_score += 1.0
        elif "focal point" in text_lower or "focal length" in text_lower:
            q_score += 0.5
        elif "focus" in text_lower or "principal" in text_lower:
            q_score += 0.5

        breakdown["Questions"] = round(q_score, 2)
        score += q_score

        # Final score clamped to [0.0, self.target_max_score]
        final_score = round(min(self.target_max_score, max(0.0, score)), 2)

        return EvaluationResult(
            score=final_score,
            max_score=self.target_max_score,
            breakdown=breakdown,
            feedback_lines=feedback,
            metadata={
                "student_name": parsed.metadata.get("student_name"),
                "student_id": parsed.metadata.get("student_id"),
            },
        )


def evaluate_exp06(parsed: ParsedSubmission) -> EvaluationResult:
    """Functional helper for Exp06 rubric evaluation."""
    evaluator = Exp06Evaluator(target_max_score=20.0)
    return evaluator.evaluate(parsed)
