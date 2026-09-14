"""Worksheet submission extractor for Computer Lab 3 (Parts A & B).

Parses student responses for conceptual physics and programming exercises
corresponding to Boxes 1 through 7 (Part A) and Boxes 8 through 17 (Part B)
from Canvas HTML online text submissions or uploaded file attachments.
"""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from typing import Any

from .base import BaseExtractor, ExtractedWorksheet, RawSubmission

logger = logging.getLogger(__name__)


class WorksheetExtractor(BaseExtractor):
    """Extractor for Computer Lab 3 Part A and Part B worksheet submissions."""

    def extract(
        self,
        submission: RawSubmission | str | bytes | Path,
        part: str = "auto",
        **kwargs: Any,
    ) -> ExtractedWorksheet:
        """Extract question boxes (1-7 or 8-17) from worksheet submission.
        
        Args:
            submission: RawSubmission, HTML text string, or file path.
            part: 'part_a', 'part_b', or 'auto' to infer from box numbers.
        """
        raw_text = self._resolve_raw_text(submission)
        cleaned_text = self.clean_text(raw_text)

        boxes = self.parse_boxes(cleaned_text)

        # Detect part if auto
        detected_part = part
        if part == "auto":
            detected_part = self._detect_part(boxes, cleaned_text)

        report = ExtractedWorksheet(
            assignment_type=detected_part,
            boxes=boxes,
            raw_text=cleaned_text,
            metadata=self._extract_metadata(submission, cleaned_text),
        )

        # Populate text_sections with box contents for standard interface access
        for b_num, content in boxes.items():
            report.text_sections[f"box_{b_num}"] = content

        # Extract numerical readings (e.g. Box 3 ruler reading)
        if 3 in boxes:
            m_b3 = re.search(r"([0-9.]+)", boxes[3])
            if m_b3:
                try:
                    report.numerical_values["box3_reading"] = float(m_b3.group(1))
                except ValueError:
                    pass

        # Check for missing boxes
        if detected_part == "part_a":
            expected = list(range(1, 8))
        elif detected_part == "part_b":
            expected = list(range(8, 18))
        else:
            expected = list(range(1, 18))

        missing = [f"Box {i}" for i in expected if i not in boxes or not boxes[i].strip()]
        report.missing_elements = missing

        if not boxes:
            report.is_valid = False
            report.extraction_warnings.append("No question box responses found in submission.")

        return report

    def _resolve_raw_text(
        self, submission: RawSubmission | str | bytes | Path
    ) -> str:
        """Resolve submission into plain/HTML text."""
        if isinstance(submission, str):
            if "\n" not in submission and len(submission) < 260:
                try:
                    p = Path(submission)
                    if p.is_file():
                        return p.read_text(encoding="utf-8", errors="replace")
                except (OSError, ValueError):
                    pass
            return submission
        if isinstance(submission, bytes):
            return submission.decode("utf-8", errors="replace")
        if isinstance(submission, Path):
            if submission.is_file():
                return submission.read_text(encoding="utf-8", errors="replace")
            return ""
        if isinstance(submission, RawSubmission):
            if submission.body_html:
                return submission.body_html
            # Check attachments for text files or HTML files
            for attach in submission.attachments:
                if "local_path" in attach and Path(attach["local_path"]).is_file():
                    p = Path(attach["local_path"])
                    if p.suffix.lower() in [".html", ".htm", ".txt", ".md"]:
                        return p.read_text(encoding="utf-8", errors="replace")
                if "bytes" in attach and isinstance(attach["bytes"], bytes):
                    return attach["bytes"].decode("utf-8", errors="replace")
        return ""

    def _extract_metadata(
        self, submission: RawSubmission | str | bytes | Path, text: str
    ) -> dict[str, Any]:
        """Extract submission metadata."""
        meta: dict[str, Any] = {}
        if isinstance(submission, RawSubmission):
            meta["user_id"] = submission.user_id
            meta["assignment_id"] = submission.assignment_id
            meta["submission_type"] = submission.submission_type
            meta["attempt"] = submission.attempt

        m_user = re.search(r"Student:\s*([^|\n]+)", text, re.IGNORECASE)
        if m_user:
            meta["student_name"] = m_user.group(1).strip()

        return meta

    def _detect_part(self, boxes: dict[int, str], text: str) -> str:
        """Detect whether submission belongs to Part A or Part B."""
        lower = text.lower()
        if "part a" in lower:
            return "part_a"
        if "part b" in lower:
            return "part_b"
        # Infer based on box number ranges
        has_part_a = any(b in boxes for b in range(1, 8))
        has_part_b = any(b in boxes for b in range(8, 18))
        if has_part_a and not has_part_b:
            return "part_a"
        if has_part_b and not has_part_a:
            return "part_b"
        return "worksheet"

    @classmethod
    def parse_boxes(cls, html_or_text: str) -> dict[int, str]:
        """Extract question boxes 1-17 from HTML or plain text string."""
        boxes: dict[int, str] = {}
        if not html_or_text:
            return boxes

        # Normalize linebreaks
        text = re.sub(r"<br\s*/?>", "\n", html_or_text)

        # Match Box N patterns
        pat = re.compile(
            r"(?:<[^>]+>\s*)*\b(?:Box|box|BOX)\s*(\d+)(?:\s*[:\-])?\s*(?:<[^>]+>\s*)*(.*?)(?=(?:<[^>]+>\s*)*\b(?:Box|box|BOX)\s*\d+(?:\s*[:\-])?|\Z)",
            re.DOTALL,
        )

        for m in pat.finditer(text):
            try:
                box_num = int(m.group(1))
            except ValueError:
                continue

            raw_content = m.group(2)
            # Remove HTML tags
            clean = re.sub(r"<[^>]+>", " ", raw_content)
            clean = html.unescape(clean).strip()
            # Strip leading colon, whitespace, or dash if not part of a negative number
            if clean.startswith((":", " ")):
                clean = re.sub(r"^[ :\t]+", "", clean)
            clean = re.sub(r"\s+", " ", clean)

            if box_num not in boxes or len(clean) > len(boxes[box_num]):
                boxes[box_num] = clean

        return boxes


# Module-level convenience functions matching test harness signatures
def parse_lab3_html(html_text: str) -> dict[int, str]:
    """Convenience wrapper to extract Box 1-17 answers from HTML."""
    return WorksheetExtractor.parse_boxes(html_text)


def parse_lab3_worksheet(
    submission: RawSubmission | str, part: str = "auto"
) -> ExtractedWorksheet:
    """Extract structured ExtractedWorksheet from submission."""
    extractor = WorksheetExtractor()
    return extractor.extract(submission, part=part)
