"""
Base classes and data models for Ulwazi SpeedGrader Rubric Evaluation Engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EvaluationResult:
    """
    Standardized rubric evaluation result across all assignments.

    Attributes:
        score: Total computed score.
        max_score: Maximum possible score (typically 20.0, or scaled sub-score 7.0/9.0/6.0).
        breakdown: Itemized scores per rubric criterion.
        feedback_lines: List of constructive feedback comments and deductions.
        metadata: Additional diagnostic or submission metadata.
        penalties_applied: Map of penalty names to deducted marks.
    """

    score: float
    max_score: float = 20.0
    breakdown: Dict[str, float] = field(default_factory=dict)
    feedback_lines: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    penalties_applied: Dict[str, float] = field(default_factory=dict)


@dataclass
class ParsedSubmission:
    """
    Normalized student submission representation output by extraction layer.

    Attributes:
        assignment_type: Assignment identifier ('exp05', 'exp06', 'lab3_part_a', etc.).
        metadata: Student metadata (student_name, student_id, group, etc.).
        text_sections: Extracted textual sections mapped by canonical key.
        tables: Parsed table structures and row counts.
        numerical_values: Extracted numerical quantities.
        uncertainties: Extracted experimental uncertainties.
        code_blocks: Extracted code snippets or VPython scripts.
        missing_elements: Identified missing report elements (e.g., 'units', 'headings').
    """

    assignment_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    text_sections: Dict[str, str] = field(default_factory=dict)
    tables: Dict[str, Any] = field(default_factory=dict)
    numerical_values: Dict[str, float] = field(default_factory=dict)
    uncertainties: Dict[str, float] = field(default_factory=dict)
    code_blocks: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)


class BaseEvaluator(ABC):
    """Abstract base evaluator defining the contract for assignment scoring engines."""

    def __init__(self, target_max_score: float = 20.0):
        self.target_max_score = float(target_max_score)

    @abstractmethod
    def evaluate(self, submission: Any) -> EvaluationResult:
        """
        Evaluate a submission against its rubric specification.

        Args:
            submission: Parsed submission object (e.g. ParsedSubmission, Dict[int, str], or str).

        Returns:
            EvaluationResult with total score, breakdown, feedback, and penalties.
        """
        pass
