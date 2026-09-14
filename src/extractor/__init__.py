"""Submission extraction and normalization package for Ulwazi Canvas SpeedGrader.

Provides extractors for laboratory report PDFs (Exp05, Exp06), online worksheets
(Lab 3 Part A, Part B), and Trinket/VPython code simulations and snapshots.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseExtractor,
    ExtractedCode,
    ExtractedPDFReport,
    ExtractedSubmission,
    ExtractedWorksheet,
    ParsedSubmission,
    RawSubmission,
)
from .code_extractor import CodeExtractor, parse_vpython_code
from .pdf_extractor import PDFExtractor, parse_exp05_pdf, parse_exp06_pdf
from .worksheet_extractor import (
    WorksheetExtractor,
    parse_lab3_html,
    parse_lab3_worksheet,
)


def parse_submission(
    submission: RawSubmission | bytes | str | Any,
    assignment_type: str,
    **kwargs: Any,
) -> ExtractedSubmission:
    """Unified entrypoint dispatching raw submissions to specialized extractors.
    
    Args:
        submission: RawSubmission object, file bytes, string, or filesystem path.
        assignment_type: One of 'exp05', 'exp06', 'lab3_part_a', 'lab3_part_b',
                         'lab3_final_code', or 'auto'.
    
    Returns:
        ExtractedSubmission (or subclass ExtractedPDFReport, ExtractedWorksheet, ExtractedCode).
    """
    atype = assignment_type.lower()

    if atype in ("exp05", "exp_05", "thermal_expansion"):
        return PDFExtractor().extract(submission, assignment_type="exp05", **kwargs)
    elif atype in ("exp06", "exp_06", "thin_lenses"):
        return PDFExtractor().extract(submission, assignment_type="exp06", **kwargs)
    elif atype in ("lab3_part_a", "part_a", "worksheet_a"):
        return WorksheetExtractor().extract(submission, part="part_a", **kwargs)
    elif atype in ("lab3_part_b", "part_b", "worksheet_b"):
        return WorksheetExtractor().extract(submission, part="part_b", **kwargs)
    elif atype in ("lab3_final_code", "final_code", "vpython", "code", "trinket"):
        return CodeExtractor().extract(submission, **kwargs)
    elif atype == "auto":
        # Attempt auto-detection based on submission attributes
        if isinstance(submission, RawSubmission):
            aid = str(submission.assignment_id)
            if aid == "316697":
                return PDFExtractor().extract(submission, assignment_type="exp05", **kwargs)
            elif aid == "316844":
                return PDFExtractor().extract(submission, assignment_type="exp06", **kwargs)
            elif aid == "315832":
                return WorksheetExtractor().extract(submission, part="part_a", **kwargs)
            elif aid == "315833":
                return WorksheetExtractor().extract(submission, part="part_b", **kwargs)
            elif aid == "315831":
                return CodeExtractor().extract(submission, **kwargs)

        # Fallback to PDF extractor auto
        return PDFExtractor().extract(submission, assignment_type="auto", **kwargs)
    else:
        # Default fallback
        return PDFExtractor().extract(submission, assignment_type=atype, **kwargs)


__all__ = [
    "BaseExtractor",
    "CodeExtractor",
    "ExtractedCode",
    "ExtractedPDFReport",
    "ExtractedSubmission",
    "ExtractedWorksheet",
    "PDFExtractor",
    "ParsedSubmission",
    "RawSubmission",
    "WorksheetExtractor",
    "parse_exp05_pdf",
    "parse_exp06_pdf",
    "parse_lab3_html",
    "parse_lab3_worksheet",
    "parse_submission",
    "parse_vpython_code",
]
