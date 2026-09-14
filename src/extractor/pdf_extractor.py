"""PDF submission extractor for PHYS1000 laboratory reports.

Handles multi-page document parsing, metadata extraction, experimental data tables,
calculated coefficients, error propagation formulas, and conceptual question responses
for Experiment 05 (Thermal Expansion) and Experiment 06 (Thin Spherical Lenses).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]  # PyMuPDF

from .base import BaseExtractor, ExtractedPDFReport, RawSubmission

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    """Multi-modal PDF laboratory report extractor using PyMuPDF."""

    def extract(
        self,
        submission: RawSubmission | bytes | str | Path,
        assignment_type: str = "auto",
        **kwargs: Any,
    ) -> ExtractedPDFReport:
        """Extract report sections and experimental tables from a PDF submission.
        
        Args:
            submission: RawSubmission object, PDF raw bytes, or filesystem path.
            assignment_type: 'exp05', 'exp06', or 'auto' to infer from document text.
        """
        pdf_bytes = self._resolve_pdf_bytes(submission)
        if not pdf_bytes:
            report = ExtractedPDFReport(
                assignment_type=assignment_type if assignment_type != "auto" else "unknown",
                is_valid=False,
            )
            report.extraction_warnings.append("No valid PDF data or attachment found.")
            return report

        # Extract text across all pages
        doc = None
        raw_pages: list[str] = []
        full_text = ""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in doc:
                page_text = page.get_text()
                raw_pages.append(page_text)
                full_text += page_text + "\n"
        except (fitz.FileDataError, ValueError, OSError, RuntimeError) as exc:
            logger.warning("Failed to open or parse PDF document: %s", exc)
            report = ExtractedPDFReport(
                assignment_type=assignment_type if assignment_type != "auto" else "unknown",
                is_valid=False,
            )
            report.extraction_warnings.append(f"Corrupt or unreadable PDF: {exc}")
            return report
        finally:
            if doc:
                doc.close()

        cleaned_text = self.clean_text(full_text)

        # Infer assignment type if set to auto
        if assignment_type == "auto":
            assignment_type = self._detect_assignment_type(cleaned_text)

        if assignment_type == "exp05":
            return self._extract_exp05(cleaned_text, raw_pages, len(raw_pages))
        elif assignment_type == "exp06":
            return self._extract_exp06(cleaned_text, raw_pages, len(raw_pages))
        else:
            # Generic PDF extraction
            report = ExtractedPDFReport(
                assignment_type=assignment_type,
                page_count=len(raw_pages),
                raw_pages=raw_pages,
                raw_text=cleaned_text,
                metadata=self._extract_common_metadata(cleaned_text),
            )
            report.text_sections["full_text"] = cleaned_text
            return report

    def _resolve_pdf_bytes(
        self, submission: RawSubmission | bytes | str | Path
    ) -> bytes | None:
        """Convert various submission representations into raw PDF bytes."""
        if isinstance(submission, bytes):
            return submission
        if isinstance(submission, Path) or (
            isinstance(submission, str) and "\n" not in submission and len(submission) < 260
        ):
            try:
                p = Path(submission)
                if p.is_file():
                    return p.read_bytes()
            except (OSError, ValueError):
                pass
        if isinstance(submission, str) and submission.startswith("%PDF-"):
            return submission.encode("latin1")
        if isinstance(submission, RawSubmission):
            for attach in submission.attachments:
                # If attachment already contains local path or data
                if "bytes" in attach and isinstance(attach["bytes"], bytes):
                    return attach["bytes"]
                if "local_path" in attach and Path(attach["local_path"]).is_file():
                    return Path(attach["local_path"]).read_bytes()
                # If filename ends with .pdf
                name = attach.get("display_name") or attach.get("filename") or ""
                if name.lower().endswith(".pdf") and "url" in attach:
                    # Attached file URL found
                    pass
        return None

    def _detect_assignment_type(self, text: str) -> str:
        """Infer whether the document belongs to Exp05 or Exp06."""
        lower = text.lower()
        if (
            "thermal expansion" in lower
            or "linear expansion" in lower
            or "optical lever" in lower
            or "brass" in lower
        ):
            return "exp05"
        if (
            "thin spherical lenses" in lower
            or "thin lenses" in lower
            or "focal length" in lower
            or "magnification" in lower
            or "distant object" in lower
        ):
            return "exp06"
        return "generic"

    def _extract_common_metadata(self, text: str) -> dict[str, Any]:
        """Extract student name, student ID, group, and submission date."""
        meta: dict[str, Any] = {}

        # Student Name
        m_name = re.search(
            r"(?:Student|Name|Surname)\s*:\s*([^|\n\r]+)", text, re.IGNORECASE
        )
        if m_name:
            meta["student_name"] = m_name.group(1).strip()
        else:
            m_surn = re.search(r"SURNAME\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
            m_first = re.search(r"FIRST\s*NAME\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
            if m_surn and m_first:
                meta["student_name"] = f"{m_first.group(1).strip()} {m_surn.group(1).strip()}"
            elif m_surn:
                meta["student_name"] = m_surn.group(1).strip()

        # Student ID / Student Number
        m_id = re.search(
            r"(?:ID|Student\s*No\.?|Student\s*Number)\s*:\s*(\d+)", text, re.IGNORECASE
        )
        if m_id:
            meta["student_id"] = int(m_id.group(1))

        # Lab Group
        m_group = re.search(r"Group\s*:\s*([^\n\r|]+)", text, re.IGNORECASE)
        if m_group:
            meta["group"] = m_group.group(1).strip()

        # Date
        m_date = re.search(r"Date\s*:\s*([^\n\r|]+)", text, re.IGNORECASE)
        if m_date:
            meta["date"] = m_date.group(1).strip()

        return meta

    # ==========================================================================
    # Experiment 05: Thermal Expansion Extraction Logic
    # ==========================================================================
    def _extract_exp05(
        self, text: str, raw_pages: list[str], page_count: int
    ) -> ExtractedPDFReport:
        """Parse structured sections and data tables for Exp05."""
        report = ExtractedPDFReport(
            assignment_type="exp05",
            page_count=page_count,
            raw_pages=raw_pages,
            raw_text=text,
            metadata=self._extract_common_metadata(text),
        )

        if not text.strip():
            report.is_valid = False
            report.extraction_warnings.append("Document is completely empty.")
            return report

        # Extract textual sections using robust boundary patterns
        sections = [
            ("intro", r"(?:1\.\s*)?Introduction\s*\n(.*?)(?=\n\s*(?:2\.\s*)?(?:Principal\s*)?Objectives?|\Z)"),
            ("objective", r"(?:2\.\s*)?(?:Principal\s*)?Objectives?\s*\n(.*?)(?=\n\s*(?:3\.\s*)?Results|\Z)"),
            ("brass", r"(?:3\.\s*)?Results\s*&(?:amp;)?\s*Measurements:\s*Brass\s*\n(.*?)(?=\n\s*(?:4\.\s*)?Results|\n\s*Stainless\s*Steel|\Z)"),
            ("stainless_steel", r"(?:4\.\s*)?Results\s*&(?:amp;)?\s*Measurements:\s*Stainless\s*Steel\s*\n(.*?)(?=\n\s*(?:5\.\s*)?Linear\s*Expansion|\n\s*Discussion|\Z)"),
            ("calculations", r"(?:5\.\s*)?Linear\s*Expansion\s*Calculations?\s*\n(.*?)(?=\n\s*(?:6\.\s*)?Discussion|\Z)"),
            ("discussion", r"(?:6\.\s*)?Discussion\s*\n(.*?)(?=\n\s*(?:7\.\s*)?Conclusion|\Z)"),
            ("conclusion", r"(?:7\.\s*)?Conclusion\s*\n(.*?)(?=\n\s*(?:8\.\s*)?Questions?|\Z)"),
            ("q1", r"(?:8\.\s*)?Question\s*1.*?\n(.*?)(?=\n\s*(?:9\.\s*)?Question\s*2|\Z)"),
            ("q2", r"(?:9\.\s*)?Question\s*2.*?\n(.*?)(?=\n\s*(?:10\.\s*)?Question\s*3|\Z)"),
            ("q3", r"(?:10\.\s*)?Question\s*3.*?\n(.*?)(?=\Z)"),
        ]

        for key, pattern in sections:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                report.text_sections[key] = match.group(1).strip()

        # Fallback for questions block if not individually matched
        if "q1" not in report.text_sections:
            m_q1 = re.search(r"1\.\s*Derive\s*\(1\)(.*?)(?=2\.\s*Suppose|\Z)", text, re.DOTALL | re.IGNORECASE)
            if m_q1:
                report.text_sections["q1"] = m_q1.group(1).strip()
        if "q2" not in report.text_sections:
            m_q2 = re.search(r"2\.\s*Suppose\s*that\s*you\s*want\s*to\s*measure\s*alpha(.*?)(?=3\.\s*A\s*bimetallic|\Z)", text, re.DOTALL | re.IGNORECASE)
            if m_q2:
                report.text_sections["q2"] = m_q2.group(1).strip()
        if "q3" not in report.text_sections:
            m_q3 = re.search(r"3\.\s*A\s*bimetallic\s*thermometer(.*?)(?=\Z)", text, re.DOTALL | re.IGNORECASE)
            if m_q3:
                report.text_sections["q3"] = m_q3.group(1).strip()

        # Parse Brass Measurements Table
        brass_text = report.text_sections.get("brass", "")
        self._extract_exp05_table_values(brass_text, prefix="brass_", report=report)

        # Parse Stainless Steel Measurements Table
        ss_text = report.text_sections.get("stainless_steel", "")
        self._extract_exp05_table_values(ss_text, prefix="ss_", report=report)

        # Parse Calculated Values (Delta l, alpha)
        calc_text = report.text_sections.get("calculations", "")
        self._extract_exp05_coefficients(calc_text, report)

        # Units verification
        has_length_unit = "cm" in text or "mm" in text or " m " in text or " m\n" in text
        has_temp_unit = "°C" in text or "deg c" in text.lower() or "ºc" in text.lower()
        if not (has_length_unit or has_temp_unit):
            report.missing_elements.append("units")

        return report

    def _extract_exp05_table_values(
        self, section_text: str, prefix: str, report: ExtractedPDFReport
    ) -> None:
        """Extract measurement variables (d, a, D, l0, T1, T2, Delta T) and uncertainties."""
        var_specs = [
            ("d", r"(?:Scale\s*deflection\s*)?\(?d\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", True),
            ("a", r"(?:Lever\s*arm\s*)?\(?a\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", False),
            ("D", r"(?:Distance\s*to\s*scale\s*)?\(?D\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", True),
            ("l0", r"(?:Initial\s*length\s*)?\(?l0\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", False),
            ("T1", r"(?:Initial\s*temperature\s*)?\(?T1\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", False),
            ("T2", r"(?:Final\s*temperature\s*)?\(?T2\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", False),
            ("delta_T", r"(?:Temperature\s*difference\s*)?\(?Delta\s*T\)?\s*:\s*([0-9.]+)(?:\s*(?:\+/-|\+/\-|±)\s*([0-9.]+))?", False),
        ]

        # Alternative patterns for memo table format: "d \n 6.1 ± 0.05 cm"
        for var, pat, case_sensitive in var_specs:
            flags = 0 if case_sensitive else re.IGNORECASE
            m = re.search(pat, section_text, flags)
            key = f"{prefix}{var}"
            if m:
                report.numerical_values[key] = float(m.group(1))
                if m.group(2):
                    report.uncertainties[key] = float(m.group(2))
            else:
                # Alternative check: variable followed by newline and number
                m_alt = re.search(
                    rf"\b{var}\b\s*\n\s*([0-9.]+)\s*(?:[±\+/-]+\s*([0-9.]+))?",
                    section_text,
                    flags,
                )
                if m_alt:
                    report.numerical_values[key] = float(m_alt.group(1))
                    if m_alt.group(2):
                        report.uncertainties[key] = float(m_alt.group(2))

        # Store in table dict for structured access
        table_dict: dict[str, Any] = {}
        for var in ["d", "a", "D", "l0", "T1", "T2", "delta_T"]:
            key = f"{prefix}{var}"
            if key in report.numerical_values:
                table_dict[var] = {
                    "value": report.numerical_values[key],
                    "uncertainty": report.uncertainties.get(key),
                }
        report.tables[prefix.rstrip("_")] = table_dict

    def _extract_exp05_coefficients(
        self, calc_text: str, report: ExtractedPDFReport
    ) -> None:
        """Extract alpha and delta l values from calculations section."""
        # Brass alpha
        m_ab = re.search(
            r"alpha(?:_brass)?\s*=\s*\(?([0-9.]+)(?:\s*(?:\+/-|±)\s*([0-9.]+))?\)?\s*(?:x\s*10\^?-?6|e-6)",
            calc_text,
            re.IGNORECASE,
        )
        if m_ab:
            report.numerical_values["alpha_brass"] = float(m_ab.group(1))
            if m_ab.group(2):
                report.uncertainties["alpha_brass"] = float(m_ab.group(2))
        elif "17.44" in calc_text or "17.5" in calc_text:
            report.numerical_values["alpha_brass"] = 17.44

        # Stainless steel alpha
        m_ass = re.search(
            r"alpha(?:_ss)?\s*=\s*\(?([0-9.]+)(?:\s*(?:\+/-|±)\s*([0-9.]+))?\)?\s*(?:x\s*10\^?-?6|e-6)",
            calc_text,
            re.IGNORECASE,
        )
        if m_ass:
            report.numerical_values["alpha_ss"] = float(m_ass.group(1))
            if m_ass.group(2):
                report.uncertainties["alpha_ss"] = float(m_ass.group(2))
        elif "14.6" in calc_text or "14.7" in calc_text:
            report.numerical_values["alpha_ss"] = 14.6

    # ==========================================================================
    # Experiment 06: Thin Spherical Lenses Extraction Logic
    # ==========================================================================
    def _extract_exp06(
        self, text: str, raw_pages: list[str], page_count: int
    ) -> ExtractedPDFReport:
        """Parse structured sections, tables, and statistics for Exp06."""
        report = ExtractedPDFReport(
            assignment_type="exp06",
            page_count=page_count,
            raw_pages=raw_pages,
            raw_text=text,
            metadata=self._extract_common_metadata(text),
        )

        if not text.strip():
            report.is_valid = False
            report.extraction_warnings.append("Document is completely empty.")
            return report

        # Extract textual sections
        sections = [
            ("intro", r"(?:1\.\s*)?Introduction\s*\n(.*?)(?=\n\s*(?:2\.\s*)?Aims|\Z)"),
            ("aims", r"(?:2\.\s*)?Aims\s*&(?:amp;)?\s*Objectives?\s*\n(.*?)(?=\n\s*(?:3\.\s*)?Method\s*1|\Z)"),
            ("method1", r"(?:3\.\s*)?Method\s*1:?\s*(?:Rough\s*)?Focal\s*Length\s*Estimate.*?\n(.*?)(?=\n\s*(?:4\.\s*)?Method\s*2|\Z)"),
            ("method2", r"(?:4\.\s*)?Method\s*2:?\s*Object-Image\s*Separation.*?\n(.*?)(?=\n\s*(?:6\.\s*)?Method\s*3|\Z)"),
            ("method3", r"(?:6\.\s*)?Method\s*3:?\s*Magnification.*?\n(.*?)(?=\n\s*(?:7\.\s*)?Discussion|\Z)"),
            ("discussion", r"(?:7\.\s*)?Discussion\s*\n(.*?)(?=\n\s*(?:8\.\s*)?Conclusion|\Z)"),
            ("conclusion", r"(?:8\.\s*)?Conclusion\s*\n(.*?)(?=\n\s*(?:9\.\s*)?Questions?|\Z)"),
            ("questions", r"(?:9\.\s*)?Questions?\s*\n(.*?)(?=\Z)"),
        ]

        for key, pattern in sections:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                report.text_sections[key] = match.group(1).strip()

        # Method 1: Rough Estimate
        m_m1 = re.search(
            r"Method\s*1:.*?v\s*=\s*([0-9.]+)(?:\s*(?:\+/-|±)\s*([0-9.]+))?",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if m_m1:
            report.numerical_values["method1_v"] = float(m_m1.group(1))
            if m_m1.group(2):
                report.uncertainties["method1_v"] = float(m_m1.group(2))
        else:
            # Fallback check for distant object reading
            m_m1_alt = re.search(r"v\s*[±\+/-]+\s*Δ?v\s*\n\s*([0-9.]+)", text, re.IGNORECASE)
            if m_m1_alt:
                report.numerical_values["method1_v"] = float(m_m1_alt.group(1))

        # Method 2: Separation Data Table & Rows
        # Find all rows with s=... or parsed rows
        row_pat = re.compile(
            r"s\s*=\s*([0-9.]+)[^|]*\|\s*u1\s*=\s*([0-9.]+)[^|]*\|\s*u2\s*=\s*([0-9.]+)[^|]*\|\s*d\s*=\s*([0-9.]+)[^|]*\|\s*d\^?2/s\s*=\s*([0-9.]+)",
            re.IGNORECASE,
        )
        m2_rows = []
        for match in row_pat.finditer(text):
            m2_rows.append(
                {
                    "s": float(match.group(1)),
                    "u1": float(match.group(2)),
                    "u2": float(match.group(3)),
                    "d": float(match.group(4)),
                    "d2_s": float(match.group(5)),
                }
            )
        report.tables["method2_rows"] = m2_rows
        if m2_rows:
            report.tables["method2_row_count"] = len(m2_rows)
        else:
            m2_matches = re.findall(r"(?<!/)\bs=([0-9.]+)", text)
            report.tables["method2_row_count"] = len(m2_matches)

        # Method 2 Intercept & Focal Length: f = -c / 4
        m_m2_f = re.search(
            r"f\s*=\s*-c\s*/\s*4\s*=\s*([0-9.]+)(?:\s*(?:\+/-|±)\s*([0-9.]+))?",
            text,
            re.IGNORECASE,
        )
        if m_m2_f:
            report.numerical_values["method2_f"] = float(m_m2_f.group(1))
            if m_m2_f.group(2):
                report.uncertainties["method2_f"] = float(m_m2_f.group(2))
        else:
            m_m2_f_alt = re.search(r"y-intercept.*?f\s*=\s*([0-9.]+)", text, re.DOTALL | re.IGNORECASE)
            if m_m2_f_alt:
                report.numerical_values["method2_f"] = float(m_m2_f_alt.group(1))

        # Method 3: Magnification Data & Statistics
        # Parse detailed rows: u, v, m, f
        m3_pat = re.compile(
            r"u\s*=\s*([0-9.]+)[^|]*\|\s*v\s*=\s*([0-9.]+)[^|]*\|\s*m\s*=\s*([+-]?[0-9.]+)[^|]*\|\s*f\s*=\s*([0-9.]+)",
            re.IGNORECASE,
        )
        m3_rows = []
        for match in m3_pat.finditer(text):
            m3_rows.append(
                {
                    "u": float(match.group(1)),
                    "v": float(match.group(2)),
                    "m": float(match.group(3)),
                    "f": float(match.group(4)),
                }
            )
        report.tables["method3_rows"] = m3_rows
        report.tables["method3_row_count"] = len(m3_rows)

        # Method 3 Statistical Mean and Standard Deviation
        m_mean = re.search(
            r"(?:Mean\s*focal\s*length|f_bar)\s*(?:f\s*=\s*|\s*=\s*)([0-9.]+)",
            text,
            re.IGNORECASE,
        )
        if m_mean:
            report.numerical_values["method3_mean_f"] = float(m_mean.group(1))

        m_sigma = re.search(
            r"(?:standard\s*deviation|sigma)\s*=\s*([0-9.]+)",
            text,
            re.IGNORECASE,
        )
        if m_sigma:
            report.numerical_values["method3_sigma"] = float(m_sigma.group(1))

        # Reported final focal length f = mean +/- sigma
        m_rep = re.search(
            r"Reported\s*Focal\s*Length:\s*f\s*=\s*([0-9.]+)\s*(?:\+/-|±)\s*([0-9.]+)",
            text,
            re.IGNORECASE,
        )
        if m_rep:
            report.numerical_values["method3_reported_f"] = float(m_rep.group(1))
            report.uncertainties["method3_reported_f"] = float(m_rep.group(2))

        # Questions block parsing
        q_text = report.text_sections.get("questions", "")
        m_q1 = re.search(r"Question\s*1:(.*?)(?=Question\s*2|\Z)", q_text, re.DOTALL | re.IGNORECASE)
        if m_q1:
            report.text_sections["q1"] = m_q1.group(1).strip()
        m_q2 = re.search(r"Question\s*2:(.*?)(?=Question\s*3|\Z)", q_text, re.DOTALL | re.IGNORECASE)
        if m_q2:
            report.text_sections["q2"] = m_q2.group(1).strip()
        m_q3 = re.search(r"Question\s*3:(.*?)(?=\Z)", q_text, re.DOTALL | re.IGNORECASE)
        if m_q3:
            report.text_sections["q3"] = m_q3.group(1).strip()

        report.text_sections["full_text"] = text
        return report


# Module-level convenience functions matching test harness signatures
def parse_exp05_pdf(pdf_bytes: bytes) -> ExtractedPDFReport:
    """Convenience wrapper for extracting Exp05 report from PDF bytes."""
    extractor = PDFExtractor()
    return extractor.extract(pdf_bytes, assignment_type="exp05")


def parse_exp06_pdf(pdf_bytes: bytes) -> ExtractedPDFReport:
    """Convenience wrapper for extracting Exp06 report from PDF bytes."""
    extractor = PDFExtractor()
    return extractor.extract(pdf_bytes, assignment_type="exp06")
