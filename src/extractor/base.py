"""Base data models and abstract extractor for Ulwazi SpeedGrader submissions.

Provides standardized dataclasses for raw submissions, normalized extracted representations,
and common extraction utilities.
"""

from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RawSubmission:
    """Raw submission data retrieved from Canvas LMS REST API or SpeedGrader DOM."""

    user_id: int
    assignment_id: int
    submission_type: str | None
    body_html: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    websnappr_url: str | None = None
    workflow_state: str = "unsubmitted"
    score: float | None = None
    attempt: int | None = None
    submitted_at: str | None = None
    url: str | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedSubmission:
    """Normalized structured representation of an extracted student submission.
    
    Compatible with downstream ParsedSubmission interface contract.
    """

    assignment_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    text_sections: dict[str, str] = field(default_factory=dict)
    tables: dict[str, Any] = field(default_factory=dict)
    numerical_values: dict[str, float] = field(default_factory=dict)
    uncertainties: dict[str, float] = field(default_factory=dict)
    code_blocks: list[str] = field(default_factory=list)
    missing_elements: list[str] = field(default_factory=list)
    raw_text: str = ""
    is_valid: bool = True
    extraction_warnings: list[str] = field(default_factory=list)


# Alias ParsedSubmission to ExtractedSubmission for interface contract compatibility
ParsedSubmission = ExtractedSubmission


@dataclass
class ExtractedPDFReport(ExtractedSubmission):
    """Specialized extracted model for laboratory report PDFs (Exp05, Exp06)."""

    page_count: int = 0
    raw_pages: list[str] = field(default_factory=list)

    @property
    def student_name(self) -> str:
        return str(self.metadata.get("student_name", ""))

    @property
    def student_id(self) -> int | None:
        val = self.metadata.get("student_id")
        return int(val) if val is not None else None

    @property
    def group(self) -> str:
        return str(self.metadata.get("group", ""))

    @property
    def is_empty(self) -> bool:
        return not bool(self.raw_text.strip())


@dataclass
class ExtractedWorksheet(ExtractedSubmission):
    """Specialized extracted model for Computer Lab 3 online worksheets (Boxes 1-17)."""

    boxes: dict[int, str] = field(default_factory=dict)

    def get_box(self, box_num: int, default: str = "") -> str:
        """Retrieve cleaned student answer for a specific question box."""
        return self.boxes.get(box_num, default)

    @property
    def box_count(self) -> int:
        return len(self.boxes)


@dataclass
class ExtractedCode(ExtractedSubmission):
    """Specialized extracted model for Computer Lab 3 Trinket / VPython simulation code."""

    source_code: str = ""
    has_scene: bool = False
    has_objects: bool = False
    has_velocity: bool = False
    has_timestep: bool = False
    has_rate: bool = False
    has_loop: bool = False
    has_euler_integration: bool = False
    has_boundary_reflection: bool = False
    syntax_valid: bool = True

    @property
    def line_count(self) -> int:
        return len(self.source_code.splitlines()) if self.source_code else 0


class BaseExtractor(ABC):
    """Abstract base class for submission extractors."""

    @abstractmethod
    def extract(
        self, submission: RawSubmission | bytes | str | Path, **kwargs: Any
    ) -> ExtractedSubmission:
        """Extract structured submission data from raw input."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Normalize whitespace, unescape HTML entities, and clean special unicode characters."""
        if not text:
            return ""
        # Unescape HTML entities
        text = html.unescape(text)
        # Normalize unicode minus, plus-minus, degrees, etc.
        text = text.replace("\u2212", "-").replace("–", "-").replace("—", "-")
        text = text.replace("\u00b1", "+/-").replace("±", "+/-")
        text = text.replace("°C", "°C").replace("º𝐶", "°C").replace("ºC", "°C")
        text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        # Normalize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text

    @staticmethod
    def parse_value_with_uncertainty(text: str) -> tuple[float | None, float | None]:
        """Parse a numerical value and its associated uncertainty from text.
        
        Examples:
            '6.1 +/- 0.05' -> (6.1, 0.05)
            '100.0 ± 0.05 cm' -> (100.0, 0.05)
            '12.0' -> (12.0, None)
        """
        cleaned = BaseExtractor.clean_text(text)
        # Match 'val +/- uncert' or 'val ± uncert'
        match = re.search(
            r"([+-]?\d+(?:\.\d+)?)\s*(?:\+/-|\+/\-|\+\-|\bpm\b|\\pm)\s*([+-]?\d+(?:\.\d+)?)",
            cleaned,
            re.IGNORECASE,
        )
        if match:
            try:
                return float(match.group(1)), float(match.group(2))
            except ValueError:
                pass

        # Match single number
        single_match = re.search(r"([+-]?\d+(?:\.\d+)?)", cleaned)
        if single_match:
            try:
                return float(single_match.group(1)), None
            except ValueError:
                pass

        return None, None
