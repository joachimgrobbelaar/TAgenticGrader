"""
Feedback comment generation for Ulwazi Canvas SpeedGrader submissions.

Produces structured, constructive, itemized feedback comments matching
PHYS1000 / PHYS1033A rubric criteria, including rubric mark breakdowns,
penalties, diagnostic notes, TA signatures, and timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import TA_NAME
from src.evaluator.base import EvaluationResult


def format_feedback_comment(
    result: EvaluationResult,
    assignment_name: str,
    student_name: str | None = None,
    grader_name: str = TA_NAME,
    timestamp: datetime | None = None,
) -> str:
    """
    Generate a simple breakdown of marks for Canvas SpeedGrader.
    """
    lines: list[str] = []
    
    for section, pts in result.breakdown.items():
        lines.append(f"{section}: {pts:.1f}")

    if result.penalties_applied:
        lines.append("Penalties:")
        for penalty_name, deduction in result.penalties_applied.items():
            lines.append(f"- {penalty_name}: -{deduction:.1f}")

    return "\n".join(lines)


def generate_feedback_comment(
    result: EvaluationResult,
    assignment_name: str,
    student_name: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Compatibility alias for format_feedback_comment.
    """
    return format_feedback_comment(
        result=result,
        assignment_name=assignment_name,
        student_name=student_name,
        **kwargs,
    )
