"""
Lab 3 Evaluator: Computer Lab 3 Online Worksheet & Final Code (PHYS1000).
Lenient scoring targeting ~65% class average.
"""

import re
from typing import Any, Dict, List, Optional

from src.evaluator.base import BaseEvaluator, EvaluationResult


class Lab3PartAEvaluator(BaseEvaluator):
    """Evaluates Lab 3 Part A (Worksheet Boxes 1-7). Lenient."""

    def __init__(self, target_max_score: float = 7.0):
        super().__init__(target_max_score=target_max_score)

    def evaluate(self, submission: Any) -> EvaluationResult:
        if isinstance(submission, dict):
            boxes = submission
        elif hasattr(submission, "text_sections"):
            boxes = submission.text_sections
        else:
            boxes = {}

        is_standalone_20 = abs(self.target_max_score - 20.0) < 0.01
        if is_standalone_20:
            allocations = {1: 2.0, 2: 3.0, 3: 3.0, 4: 2.0, 5: 4.0, 6: 3.0, 7: 3.0}
        else:
            allocations = {i: 1.0 for i in range(1, 8)}

        score = 0.0
        breakdown: Dict[str, float] = {}
        feedback: List[str] = []

        filled = sum(1 for i in range(1, 8) if str(boxes.get(i, "")).strip())

        for box_id in range(1, 8):
            b = str(boxes.get(box_id, "")).strip()
            alloc = allocations[box_id]

            if not b:
                # Participation credit if most boxes filled
                if filled >= 4:
                    pts = round(alloc * 0.25, 2)
                    breakdown[f"Box {box_id}"] = pts
                    score += pts
                else:
                    breakdown[f"Box {box_id}"] = 0.0
                continue

            b_lower = b.lower()
            got_full = False

            if box_id == 1:
                got_full = any(k in b_lower for k in ("straight", "constant", "velocity", "line", "motion"))
            elif box_id == 2:
                got_full = ("r" in b and "v" in b) or any(k in b_lower for k in ("position", "vector", "kinematic"))
            elif box_id == 3:
                m = re.search(r"([0-9.]+)", b)
                if m:
                    val = float(m.group(1))
                    got_full = (30.0 <= val <= 36.0) or (3.0 <= val <= 3.6) or (0.030 <= val <= 0.036)
                else:
                    got_full = any(k in b_lower for k in ("mm", "cm", "ruler", "contact"))
            elif box_id == 4:
                got_full = any(k in b_lower for k in ("-p", "reverse", "opposite", "momentum", "elastic"))
            elif box_id == 5:
                got_full = any(k in b_lower for k in ("closed", "isolated", "system", "force", "matter"))
            elif box_id == 6:
                got_full = any(k in b_lower for k in ("-p", "vector", "component", "momentum", "vertical"))
            elif box_id == 7:
                got_full = any(k in b_lower for k in ("-p", "vector", "component", "momentum", "horizontal"))

            if got_full:
                breakdown[f"Box {box_id}"] = alloc
                score += alloc
            else:
                half = round(alloc * 0.6, 2)
                breakdown[f"Box {box_id}"] = half
                score += half

        final_score = round(min(self.target_max_score, max(0.0, score)), 2)
        return EvaluationResult(score=final_score, max_score=self.target_max_score,
                                breakdown=breakdown, feedback_lines=feedback)


class Lab3PartBEvaluator(BaseEvaluator):
    """Evaluates Lab 3 Part B (Worksheet Boxes 8-17). Lenient."""

    def __init__(self, target_max_score: float = 9.0):
        super().__init__(target_max_score=target_max_score)

    def evaluate(self, submission: Any) -> EvaluationResult:
        if isinstance(submission, dict):
            boxes = submission
        elif hasattr(submission, "text_sections"):
            boxes = submission.text_sections
        else:
            boxes = {}

        is_standalone_20 = abs(self.target_max_score - 20.0) < 0.01
        unit_pt = 2.0 if is_standalone_20 else 0.9

        score = 0.0
        breakdown: Dict[str, float] = {}
        feedback: List[str] = []

        filled = sum(1 for i in range(8, 18) if str(boxes.get(i, "")).strip())

        keywords = {
            8: ("time", "stationary", "elapsed", "zero", "initial", "start", "rest"),
            9: ("constant", "zero", "net force", "newton", "velocity", "first law"),
            10: ("agree", "assignment", "memory", "code", "equal", "update", "increment"),
            11: ("single", "tiny", "step", "stationary", "small", "brief", "imperceptible"),
            12: ("through", "passes", "northeast", "wall", "continue", "beyond"),
            13: ("bounce", "reverse", "reflect", "elastic", "collision", "rebound"),
            14: ("-v_x", "-vx", "reverse", "opposite", "invert", "negative", "change"),
            15: ("left", "reverse", "collid", "bounce", "wall", "back", "return"),
            16: ("bounc", "upward", "drift", "normal", "force", "newton", "elastic", "3rd"),
            17: ("all", "four", "enclosure", "reflect", "box", "wall", "contain"),
        }

        for box_id in range(8, 18):
            b = str(boxes.get(box_id, "")).strip()
            b_lower = b.lower()

            if not b:
                if filled >= 5:
                    pts = round(unit_pt * 0.25, 2)
                    breakdown[f"Box {box_id}"] = pts
                    score += pts
                else:
                    breakdown[f"Box {box_id}"] = 0.0
                continue

            kws = keywords.get(box_id, ())
            got_full = any(k in b_lower for k in kws)

            if got_full:
                breakdown[f"Box {box_id}"] = unit_pt
                score += unit_pt
            else:
                half = round(unit_pt * 0.6, 2)
                breakdown[f"Box {box_id}"] = half
                score += half

        final_score = round(min(self.target_max_score, max(0.0, score)), 2)
        return EvaluationResult(score=final_score, max_score=self.target_max_score,
                                breakdown=breakdown, feedback_lines=feedback)


class Lab3FinalCodeEvaluator(BaseEvaluator):
    """Evaluates Lab 3 Final Code (VPython simulation). Lenient."""

    def __init__(self, target_max_score: float = 6.0):
        super().__init__(target_max_score=target_max_score)

    def evaluate(self, submission: Any) -> EvaluationResult:
        code_str = str(submission)
        is_standalone_20 = abs(self.target_max_score - 20.0) < 0.01

        if not code_str.strip():
            keys = ["Scene Setup", "Variables Setup", "Animation Loop",
                    "Euler Integration", "Collision Logic"]
            if is_standalone_20:
                keys.append("Stability & Syntax")
            return EvaluationResult(score=0.0, max_score=self.target_max_score,
                                    breakdown={k: 0.0 for k in keys},
                                    feedback_lines=["No submission found for this assignment."])

        score = 0.0
        breakdown: Dict[str, float] = {}
        feedback: List[str] = []
        code_lower = code_str.lower()

        if is_standalone_20:
            allocs = {"scene": 4.0, "vars": 3.0, "loop": 3.0,
                      "euler": 4.0, "collision": 4.0, "stability": 2.0}
        else:
            allocs = {"scene": 1.0, "vars": 1.0, "loop": 1.0,
                      "euler": 1.0, "collision": 2.0, "stability": 0.0}

        # Scene setup - very lenient
        if "sphere(" in code_str and "box(" in code_str:
            breakdown["Scene Setup"] = allocs["scene"]
            score += allocs["scene"]
        elif "sphere(" in code_str or "box(" in code_str or "canvas" in code_lower:
            pts = round(allocs["scene"] * 0.7, 2)
            breakdown["Scene Setup"] = pts
            score += pts
        elif any(k in code_lower for k in ("vpython", "glowscript", "trinket", "http")):
            pts = round(allocs["scene"] * 0.5, 2)
            breakdown["Scene Setup"] = pts
            score += pts
        else:
            breakdown["Scene Setup"] = 0.0

        # Variables - very lenient
        if "velocity" in code_str or "vel" in code_lower:
            breakdown["Variables Setup"] = allocs["vars"]
            score += allocs["vars"]
        elif "dt" in code_str or "delta" in code_lower or "speed" in code_lower:
            pts = round(allocs["vars"] * 0.7, 2)
            breakdown["Variables Setup"] = pts
            score += pts
        elif code_str.strip():
            pts = round(allocs["vars"] * 0.3, 2)
            breakdown["Variables Setup"] = pts
            score += pts
        else:
            breakdown["Variables Setup"] = 0.0

        # Animation loop
        if "while" in code_str and "rate(" in code_str:
            breakdown["Animation Loop"] = allocs["loop"]
            score += allocs["loop"]
        elif "while" in code_str or "for" in code_str or "loop" in code_lower:
            pts = round(allocs["loop"] * 0.7, 2)
            breakdown["Animation Loop"] = pts
            score += pts
        elif code_str.strip():
            pts = round(allocs["loop"] * 0.3, 2)
            breakdown["Animation Loop"] = pts
            score += pts
        else:
            breakdown["Animation Loop"] = 0.0

        # Euler integration
        if "ball.pos" in code_str or ".pos" in code_str:
            breakdown["Euler Integration"] = allocs["euler"]
            score += allocs["euler"]
        elif "pos" in code_lower or "position" in code_lower:
            pts = round(allocs["euler"] * 0.5, 2)
            breakdown["Euler Integration"] = pts
            score += pts
        else:
            breakdown["Euler Integration"] = 0.0

        # Collision logic
        c_score = 0.0
        unit_c = allocs["collision"] * 0.5
        if ".velocity.x" in code_str or "vel.x" in code_lower or "vx" in code_lower:
            c_score += unit_c
        if ".velocity.y" in code_str or "vel.y" in code_lower or "vy" in code_lower:
            c_score += unit_c
        if c_score == 0 and ("if" in code_str and ("pos" in code_lower or "wall" in code_lower)):
            c_score = round(allocs["collision"] * 0.5, 2)
        elif c_score == 0 and code_str.strip():
            c_score = round(allocs["collision"] * 0.25, 2)
        breakdown["Collision Logic"] = round(c_score, 2)
        score += c_score

        # Stability (standalone only)
        if is_standalone_20:
            breakdown["Stability & Syntax"] = allocs["stability"]
            score += allocs["stability"]

        final_score = round(min(self.target_max_score, max(0.0, score)), 2)
        return EvaluationResult(score=final_score, max_score=self.target_max_score,
                                breakdown=breakdown, feedback_lines=feedback)


class Lab3Evaluator(BaseEvaluator):
    """Unified evaluator for all Lab 3 components."""

    def __init__(self, target_max_score: float = 20.0):
        super().__init__(target_max_score=target_max_score)
        self.evaluator_a = Lab3PartAEvaluator(target_max_score=7.0)
        self.evaluator_b = Lab3PartBEvaluator(target_max_score=9.0)
        self.evaluator_code = Lab3FinalCodeEvaluator(target_max_score=6.0)

    def evaluate(self, submission: Any, component: Optional[str] = None) -> EvaluationResult:
        if component == "part_a":
            return self.evaluator_a.evaluate(submission)
        elif component == "part_b":
            return self.evaluator_b.evaluate(submission)
        elif component in ("final_code", "code"):
            return self.evaluator_code.evaluate(submission)

        if isinstance(submission, str):
            return self.evaluator_code.evaluate(submission)
        elif isinstance(submission, dict):
            keys = set(submission.keys())
            if any(k in range(1, 8) for k in keys) and not any(k in range(8, 18) for k in keys):
                return self.evaluator_a.evaluate(submission)
            if any(k in range(8, 18) for k in keys) and not any(k in range(1, 8) for k in keys):
                return self.evaluator_b.evaluate(submission)

            res_a = self.evaluator_a.evaluate(submission.get("part_a", {}))
            res_b = self.evaluator_b.evaluate(submission.get("part_b", {}))
            res_code = self.evaluator_code.evaluate(submission.get("code", ""))

            composite = round(res_a.score + res_b.score + res_code.score, 2)
            breakdown = {}
            breakdown.update({f"Part A - {k}": v for k, v in res_a.breakdown.items()})
            breakdown.update({f"Part B - {k}": v for k, v in res_b.breakdown.items()})
            breakdown.update({f"Final Code - {k}": v for k, v in res_code.breakdown.items()})
            fb = res_a.feedback_lines + res_b.feedback_lines + res_code.feedback_lines
            return EvaluationResult(score=composite, max_score=20.0, breakdown=breakdown, feedback_lines=fb)

        return self.evaluator_a.evaluate({})


# Functional entrypoints
def evaluate_lab3_part_a(boxes: Dict[int, str], target_max_score: float = 7.0) -> EvaluationResult:
    return Lab3PartAEvaluator(target_max_score=target_max_score).evaluate(boxes)

def evaluate_lab3_part_b(boxes: Dict[int, str], target_max_score: float = 9.0) -> EvaluationResult:
    return Lab3PartBEvaluator(target_max_score=target_max_score).evaluate(boxes)

def evaluate_lab3_final_code(code_str: str, target_max_score: float = 6.0) -> EvaluationResult:
    return Lab3FinalCodeEvaluator(target_max_score=target_max_score).evaluate(code_str)

def evaluate_lab3(submission: Any, component: Optional[str] = None) -> EvaluationResult:
    return Lab3Evaluator(target_max_score=20.0).evaluate(submission, component=component)
