"""
Test Harness & Reference Evaluation Engine for Ulwazi Grading Agent.
Encodes the authoritative interface contracts, PDF/HTML extraction parsers,
rubric scoring rules (from memo_specifications.md), and SpeedGrader posting helpers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
import fitz  # PyMuPDF
import requests


# --- 1. Data Contracts (from PROJECT.md Interface Contracts) ---

@dataclass
class CanvasSession:
    cookies: List[Dict[str, Any]]
    csrf_token: str
    storage_state_path: Optional[str] = None

    def get_cookie_header(self) -> str:
        return "; ".join(f"{c['name']}={c['value']}" for c in self.cookies)


@dataclass
class RawSubmission:
    user_id: int
    assignment_id: int
    submission_type: Optional[str]
    body_html: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    websnappr_url: Optional[str] = None
    workflow_state: str = "unsubmitted"
    score: Optional[float] = None


@dataclass
class ParsedSubmission:
    assignment_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    text_sections: Dict[str, str] = field(default_factory=dict)
    tables: Dict[str, Any] = field(default_factory=dict)
    numerical_values: Dict[str, float] = field(default_factory=dict)
    uncertainties: Dict[str, float] = field(default_factory=dict)
    code_blocks: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    score: float
    max_score: float = 20.0
    breakdown: Dict[str, float] = field(default_factory=dict)
    feedback_lines: List[str] = field(default_factory=list)
    penalties_applied: Dict[str, float] = field(default_factory=dict)


@dataclass
class SubmissionReceipt:
    status: str
    assignment_id: int
    user_id: int
    score: float
    comment_posted: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --- 2. Extraction & Parsing Helpers ---

def parse_exp05_pdf(pdf_bytes: bytes) -> ParsedSubmission:
    """Parses text, metadata, tables, and questions from an Exp05 report PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    parsed = ParsedSubmission(assignment_type="exp05")

    # Extract metadata
    m_student = re.search(r"Student:\s*([^|\n]+)", full_text)
    if m_student:
        parsed.metadata["student_name"] = m_student.group(1).strip()
    m_id = re.search(r"ID:\s*(\d+)", full_text)
    if m_id:
        parsed.metadata["student_id"] = int(m_id.group(1))
    m_group = re.search(r"Group:\s*([^\n|]+)", full_text)
    if m_group:
        parsed.metadata["group"] = m_group.group(1).strip()

    # Section text extraction with newline boundary to avoid matching numbers like 5.1
    sections = [
        ("intro", r"1\.\s*Introduction\s*\n(.*?)(?=\n\s*2\.|\Z)"),
        ("objective", r"2\.\s*Principal Objectives?\s*\n(.*?)(?=\n\s*3\.|\Z)"),
        ("brass", r"3\.\s*Results & Measurements:\s*Brass\s*\n(.*?)(?=\n\s*4\.|\Z)"),
        ("stainless_steel", r"4\.\s*Results & Measurements:\s*Stainless Steel\s*\n(.*?)(?=\n\s*5\.|\Z)"),
        ("calculations", r"5\.\s*Linear Expansion Calculations\s*\n(.*?)(?=\n\s*6\.|\Z)"),
        ("discussion", r"6\.\s*Discussion\s*\n(.*?)(?=\n\s*7\.|\Z)"),
        ("conclusion", r"7\.\s*Conclusion\s*\n(.*?)(?=\n\s*8\.|\Z)"),
        ("q1", r"8\.\s*Question 1.*?\n(.*?)(?=\n\s*9\.|\Z)"),
        ("q2", r"9\.\s*Question 2.*?\n(.*?)(?=\n\s*10\.|\Z)"),
        ("q3", r"10\.\s*Question 3.*?\n(.*?)(?=\Z)"),
    ]
    for key, pattern in sections:
        match = re.search(pattern, full_text, re.DOTALL | re.IGNORECASE)
        if match:
            parsed.text_sections[key] = match.group(1).strip()

    # Extract brass table variables
    brass_text = parsed.text_sections.get("brass", "")
    for var, key in [("d", "brass_d"), ("a", "brass_a"), ("D", "brass_D"), ("l0", "brass_l0"), ("Delta T", "brass_delta_T")]:
        m_val = re.search(rf"{var}\)?:\s*([0-9.]+)", brass_text)
        if m_val:
            parsed.numerical_values[key] = float(m_val.group(1))

    # Extract SS table variables
    ss_text = parsed.text_sections.get("stainless_steel", "")
    for var, key in [("d", "ss_d"), ("a", "ss_a"), ("D", "ss_D"), ("l0", "ss_l0"), ("Delta T", "ss_delta_T")]:
        m_val = re.search(rf"{var}\)?:\s*([0-9.]+)", ss_text)
        if m_val:
            parsed.numerical_values[key] = float(m_val.group(1))

    # Units check
    if "cm" not in full_text and "°C" not in full_text:
        parsed.missing_elements.append("units")

    return parsed


def parse_exp06_pdf(pdf_bytes: bytes) -> ParsedSubmission:
    """Parses text, tables, and questions from an Exp06 Thin Lenses report PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    parsed = ParsedSubmission(assignment_type="exp06")

    m_student = re.search(r"Student:\s*([^|\n]+)", full_text)
    if m_student:
        parsed.metadata["student_name"] = m_student.group(1).strip()
    m_id = re.search(r"ID:\s*(\d+)", full_text)
    if m_id:
        parsed.metadata["student_id"] = int(m_id.group(1))

    # Method 1 rough estimate (only search in Method 1 section)
    m_m1 = re.search(r"Method 1:.*?v\s*=\s*([0-9.]+)", full_text, re.DOTALL | re.IGNORECASE)
    if m_m1:
        parsed.numerical_values["method1_v"] = float(m_m1.group(1))

    # Method 2 rows count (exclude d^2/s)
    m2_matches = re.findall(r"(?<!/)\bs=([0-9.]+)", full_text)
    parsed.tables["method2_row_count"] = len(m2_matches)

    # Method 2 intercept focal length
    m_m2_f = re.search(r"f\s*=\s*-c\s*/\s*4\s*=\s*([0-9.]+)", full_text)
    if m_m2_f:
        parsed.numerical_values["method2_f"] = float(m_m2_f.group(1))

    # Method 3 stats
    m_m3_mean = re.search(r"Mean focal length.*?=\s*([0-9.]+)", full_text, re.IGNORECASE)
    if m_m3_mean:
        parsed.numerical_values["method3_mean_f"] = float(m_m3_mean.group(1))

    m_m3_sigma = re.search(r"standard deviation.*?=\s*([0-9.]+)", full_text, re.IGNORECASE)
    if m_m3_sigma:
        parsed.numerical_values["method3_sigma"] = float(m_m3_sigma.group(1))

    parsed.text_sections["full_text"] = full_text
    return parsed


def parse_lab3_html(html_text: str) -> Dict[int, str]:
    """Extracts text content for Boxes 1-17 from Lab 3 worksheet HTML submission, stripping HTML tags."""
    boxes: Dict[int, str] = {}
    matches = re.findall(r"Box\s*(\d+):?</b>(.*?)(?=<p><b>Box|</p>|\Z)", html_text, re.DOTALL | re.IGNORECASE)
    for box_num_str, raw_content in matches:
        clean_content = re.sub(r"<[^>]+>", "", raw_content).strip()
        boxes[int(box_num_str)] = clean_content
    return boxes


# --- 3. Rubric Evaluation Engines (from memo_specifications.md) ---

def evaluate_exp05(parsed: ParsedSubmission) -> EvaluationResult:
    """
    Evaluates Exp05 report against 20-point rubric:
    - Intro: 1.0
    - Objective: 1.0
    - Brass Table: 3.5 (0.5 * 7 variables: d, a, D, l0, T1, T2, Delta T)
    - Stainless Steel Table: 3.5 (0.5 * 7 variables)
    - Linear Expansion Coefficients: 3.0 (1.5 brass, 1.5 ss)
    - Discussion: 1.0
    - Conclusion: 2.0 (1.0 comparison, 1.0 Kaye & Laby accepted literature reference)
    - Q1: 2.0 (1.0 reflection angle factor of 2, 1.0 small-angle approx)
    - Q2: 2.0 (Formula + accuracy calculation: accepts 14% memo or 6.1% standard)
    - Q3: 1.0 (Direction towards SS: 0.5 explanation, 0.5 sketch/curvature)
    Total: 20.0 points.
    """
    score = 0.0
    breakdown: Dict[str, float] = {}
    feedback: List[str] = []

    # 1. Introduction (1.0)
    intro_txt = parsed.text_sections.get("intro", "")
    if "thermal expansion" in intro_txt.lower() and "alpha" in intro_txt.lower():
        breakdown["Introduction"] = 1.0
        score += 1.0
    elif intro_txt:
        breakdown["Introduction"] = 0.5
        score += 0.5
        feedback.append("Introduction lacked explicit definition of alpha.")
    else:
        breakdown["Introduction"] = 0.0
        feedback.append("Introduction section missing.")

    # 2. Objective (1.0)
    obj_txt = parsed.text_sections.get("objective", "")
    if "alpha" in obj_txt.lower() and "error" in obj_txt.lower():
        breakdown["Objectives"] = 1.0
        score += 1.0
    elif obj_txt:
        breakdown["Objectives"] = 0.5
        score += 0.5
        feedback.append("Objective should include error analysis.")
    else:
        breakdown["Objectives"] = 0.0
        feedback.append("Principal Objective missing.")

    # 3. Brass Table (3.5 marks: 7 variables x 0.5)
    brass_txt = parsed.text_sections.get("brass", "")
    brass_vars = sum(1 for v in ["d", "a", "D", "l0", "T1", "T2", "Delta T"] if v in brass_txt)
    b_score = min(3.5, brass_vars * 0.5)
    breakdown["Brass Table"] = b_score
    score += b_score
    if b_score < 3.5:
        feedback.append(f"Brass table incomplete ({brass_vars}/7 measurements provided).")

    # 4. SS Table (3.5 marks: 7 variables x 0.5)
    ss_txt = parsed.text_sections.get("stainless_steel", "")
    ss_vars = sum(1 for v in ["d", "a", "D", "l0", "T1", "T2", "Delta T"] if v in ss_txt)
    ss_score = min(3.5, ss_vars * 0.5)
    breakdown["Stainless Steel Table"] = ss_score
    score += ss_score
    if ss_score < 3.5:
        feedback.append(f"Stainless steel table incomplete ({ss_vars}/7 measurements provided).")

    # 5. Linear Expansion Coefficients (3.0 marks: 1.5 each)
    calc_txt = parsed.text_sections.get("calculations", "")
    c_score = 0.0
    if "17.4" in calc_txt or "17.5" in calc_txt:
        c_score += 1.5
    if "14.6" in calc_txt or "14.7" in calc_txt:
        c_score += 1.5
    breakdown["Linear Expansion Coefficients"] = c_score
    score += c_score

    # 6. Discussion (1.0)
    disc_txt = parsed.text_sections.get("discussion", "")
    if disc_txt and len(disc_txt.split()) > 10:
        breakdown["Discussion"] = 1.0
        score += 1.0
    else:
        breakdown["Discussion"] = 0.0
        feedback.append("Discussion section is superficial or missing.")

    # 7. Conclusion (2.0)
    conc_txt = parsed.text_sections.get("conclusion", "")
    conc_score = 0.0
    if "kaye" in conc_txt.lower() or "literature" in conc_txt.lower() or "accepted" in conc_txt.lower():
        conc_score += 1.0
    if "17.4" in conc_txt or "14.6" in conc_txt or "agreement" in conc_txt.lower():
        conc_score += 1.0
    breakdown["Conclusion"] = conc_score
    score += conc_score
    if conc_score < 2.0:
        feedback.append("Conclusion must reference accepted literature values (Kaye & Laby).")

    # 8. Questions (5.0 total)
    # Q1: Optical lever derivation (2.0)
    q1_txt = parsed.text_sections.get("q1", "")
    q1_score = 0.0
    if "2" in q1_txt and ("reflection" in q1_txt.lower() or "2*theta" in q1_txt or "2 * d" in q1_txt or "2*D" in q1_txt or "2D" in q1_txt):
        q1_score += 1.0
    if "tan" in q1_txt or "small-angle" in q1_txt.lower() or "approx" in q1_txt:
        q1_score += 1.0
    breakdown["Question 1"] = q1_score
    score += q1_score
    if q1_score < 2.0:
        feedback.append("Q1: Remember the optical lever reflection angle factor of 2.")

    # Q2: 10% accuracy calculation (2.0) - Accepts memo's 14% or standard 6.1%
    q2_txt = parsed.text_sections.get("q2", "")
    q2_score = 0.0
    if "14%" in q2_txt or "14 %" in q2_txt or "0.14" in q2_txt or "6.1%" in q2_txt or "6%" in q2_txt or "0.061" in q2_txt:
        q2_score = 2.0
    elif q2_txt:
        q2_score = 1.0
        feedback.append("Q2: Review error budget calculation for required scale accuracy.")
    breakdown["Question 2"] = q2_score
    score += q2_score

    # Q3: Bimetallic strip (1.0)
    q3_txt = parsed.text_sections.get("q3", "")
    q3_score = 0.0
    if "stainless" in q3_txt.lower() and ("bend" in q3_txt.lower() or "curve" in q3_txt.lower()):
        q3_score = 1.0
    elif q3_txt:
        q3_score = 0.5
        feedback.append("Q3: Bimetallic strip bends towards the material with lower expansion (stainless steel).")
    breakdown["Question 3"] = q3_score
    score += q3_score

    # Units penalty check
    penalties = {}
    if "units" in parsed.missing_elements:
        penalties["Units Omitted"] = 0.5
        score = max(0.0, score - 0.5)

    return EvaluationResult(
        score=round(min(20.0, max(0.0, score)), 2),
        max_score=20.0,
        breakdown=breakdown,
        feedback_lines=feedback,
        penalties_applied=penalties,
    )


def evaluate_exp06(parsed: ParsedSubmission) -> EvaluationResult:
    """
    Evaluates Exp06 report against 20-point rubric:
    - Intro: 1.0
    - Aims: 1.0
    - Method 1 (Rough Estimate): 1.0 (0.5 principle, 0.5 value)
    - Method 2 (Separation): 7.0 (2.5 data table, 1.5 formulas, 1.0 plot, 1.0 intercept & f error, 1.0 linearization)
    - Method 3 (Magnification): 5.0 (1.0 formulas, 2.0 data table, 0.5 mean, 0.5 sigma, 1.0 reported f)
    - Discussion: 1.0
    - Conclusion: 1.0
    - Q1: 1.0 (Minus sign inversion)
    - Q2: 1.0 (Lens maker limit u -> infinity)
    - Q3: 1.0 (Focal point and length definitions)
    Total: 20.0 points.
    """
    score = 0.0
    breakdown: Dict[str, float] = {}
    feedback: List[str] = []
    text = parsed.text_sections.get("full_text", "")

    if not text.strip():
        return EvaluationResult(
            score=0.0,
            max_score=20.0,
            breakdown={
                "Introduction": 0.0, "Aims": 0.0, "Method 1": 0.0, "Method 2": 0.0,
                "Method 3": 0.0, "Discussion": 0.0, "Conclusion": 0.0, "Questions": 0.0
            },
            feedback_lines=["Document is empty."],
        )

    # Intro (1.0)
    if "converging" in text.lower() and "thin" in text.lower():
        breakdown["Introduction"] = 1.0
        score += 1.0
    else:
        breakdown["Introduction"] = 0.5
        score += 0.5

    # Aims (1.0)
    if "methods" in text.lower() or "aims" in text.lower():
        breakdown["Aims"] = 1.0
        score += 1.0
    else:
        breakdown["Aims"] = 0.5
        score += 0.5

    # Method 1 (1.0)
    m1_v = parsed.numerical_values.get("method1_v", 0.0)
    if 11.0 <= m1_v <= 12.0:
        breakdown["Method 1"] = 1.0
        score += 1.0
    elif m1_v > 0:
        breakdown["Method 1"] = 0.5
        score += 0.5
        feedback.append("Method 1 reading deviates from expected focal range.")
    else:
        breakdown["Method 1"] = 0.0
        feedback.append("Method 1 rough focal estimate missing.")

    # Method 2 (7.0)
    m2_rows = parsed.tables.get("method2_row_count", 0)
    m2_score = min(2.5, m2_rows * 0.42)  # table: 2.5
    if "d^2/s" in text or "linearization" in text.lower():
        m2_score += 2.0  # linearization & formulas: 2.0
    if ("worst fit" in text.lower() and "omitted" not in text.lower()) or "2 lines of worst fit" in text.lower():
        m2_score += 1.5  # plot with worst fit: 1.5
    else:
        feedback.append("Method 2 plot requires 2 lines of worst fit and centroid.")
    m2_f = parsed.numerical_values.get("method2_f", 0.0)
    if 11.5 <= m2_f <= 12.5:
        m2_score += 1.0  # focal length determination: 1.0
    m2_score = min(7.0, m2_score)
    breakdown["Method 2"] = round(m2_score, 2)
    score += m2_score

    # Method 3 (5.0)
    m3_mean = parsed.numerical_values.get("method3_mean_f", 0.0)
    m3_sigma = parsed.numerical_values.get("method3_sigma", 0.0)
    m3_score = 0.0
    if "m = -v/u" in text or "magnification" in text.lower():
        m3_score += 1.0  # formula: 1.0
    if "u=15" in text or "u=18" in text:
        m3_score += 2.0  # table: 2.0
    if 11.8 <= m3_mean <= 12.2:
        m3_score += 1.0  # mean: 1.0
    if 0.005 <= m3_sigma <= 0.05:
        m3_score += 1.0  # std dev & reported: 1.0
    m3_score = min(5.0, m3_score)
    breakdown["Method 3"] = round(m3_score, 2)
    score += m3_score

    # Discussion & Conclusion (2.0)
    if "method 1" in text.lower() and "method 2" in text.lower() and "method 3" in text.lower():
        breakdown["Discussion"] = 1.0
        score += 1.0
    else:
        breakdown["Discussion"] = 0.5
        score += 0.5
        feedback.append("Discussion must compare the three experimental methods.")

    if "conclusion" in text.lower() and "12" in text:
        breakdown["Conclusion"] = 1.0
        score += 1.0
    else:
        breakdown["Conclusion"] = 0.5
        score += 0.5

    # Questions 1-3 (3.0)
    q_score = 0.0
    if "question 1" in text.lower() and "inverted" in text.lower():
        q_score += 1.0
    elif "question 1" in text.lower():
        feedback.append("Q1: Minus sign in magnification indicates inverted image.")
    if "question 2" in text.lower() and ("infinity" in text.lower() or "1/u" in text):
        q_score += 1.0
    if "question 3" in text.lower() and "focal point" in text.lower():
        q_score += 1.0
    breakdown["Questions"] = q_score
    score += q_score

    return EvaluationResult(
        score=round(min(20.0, max(0.0, score)), 2),
        max_score=20.0,
        breakdown=breakdown,
        feedback_lines=feedback,
    )


def evaluate_lab3_part_a(boxes: Dict[int, str]) -> EvaluationResult:
    """Evaluates Lab 3 Part A (Boxes 1-7, 7.0 pts scaled or 20.0 standalone)."""
    score = 0.0
    breakdown: Dict[str, float] = {}
    feedback: List[str] = []

    # Box 1: Straight line at constant velocity (1.0 pt)
    b1 = boxes.get(1, "").lower()
    if "straight" in b1 and "constant" in b1:
        breakdown["Box 1"] = 1.0
        score += 1.0
    elif b1:
        breakdown["Box 1"] = 0.5
        score += 0.5
    else:
        breakdown["Box 1"] = 0.0
        feedback.append("Box 1: Describe straight-line motion at constant velocity.")

    # Box 2: r_f = r_i + v*t (1.0 pt)
    b2 = boxes.get(2, "")
    if "r" in b2 and "v" in b2 and "t" in b2:
        breakdown["Box 2"] = 1.0
        score += 1.0
    else:
        breakdown["Box 2"] = 0.0
        feedback.append("Box 2: State vector position formula r_f = r_i + v*t.")

    # Box 3: Ruler reading in [32.0, 34.0] mm, [3.2, 3.4] cm, [0.032, 0.034] m (1.0 pt)
    b3 = boxes.get(3, "").lower()
    m_b3 = re.search(r"([0-9.]+)", b3)
    if m_b3:
        val = float(m_b3.group(1))
        if (32.0 <= val <= 34.0) or (3.2 <= val <= 3.4) or (0.032 <= val <= 0.034):
            breakdown["Box 3"] = 1.0
            score += 1.0
        else:
            breakdown["Box 3"] = 0.0
            feedback.append("Box 3: Reading outside acceptable range [32.0, 34.0] mm.")
    else:
        breakdown["Box 3"] = 0.0
        feedback.append("Box 3: Contact distance is 33 +/- 0.5 mm.")

    # Box 4: -p_x (1.0 pt)
    b4 = boxes.get(4, "").lower()
    if "-p_x" in b4 or "-px" in b4 or "- p_x" in b4:
        breakdown["Box 4"] = 1.0
        score += 1.0
    else:
        breakdown["Box 4"] = 0.0
        feedback.append("Box 4: Momentum reverses sign (-p_x) on elastic reflection.")

    # Box 5: Closed but not isolated (1.0 pt)
    b5 = boxes.get(5, "").lower()
    if "closed" in b5 and "isolated" in b5:
        breakdown["Box 5"] = 1.0
        score += 1.0
    else:
        breakdown["Box 5"] = 0.5
        score += 0.5
        feedback.append("Box 5: System is closed (no matter transfer) but not isolated (external normal force acts).")

    # Box 6: -p_x i + p_y j (1.0 pt)
    b6 = boxes.get(6, "")
    if "-p_x" in b6 or "-px" in b6 or "- p_x" in b6 or "- px" in b6:
        breakdown["Box 6"] = 1.0
        score += 1.0
    else:
        breakdown["Box 6"] = 0.0

    # Box 7: p_x i - p_y j (1.0 pt)
    b7 = boxes.get(7, "")
    if "-p_y" in b7 or "-py" in b7 or "- p_y" in b7 or "- py" in b7:
        breakdown["Box 7"] = 1.0
        score += 1.0
    else:
        breakdown["Box 7"] = 0.0

    return EvaluationResult(score=round(score, 2), max_score=7.0, breakdown=breakdown, feedback_lines=feedback)


def evaluate_lab3_part_b(boxes: Dict[int, str]) -> EvaluationResult:
    """Evaluates Lab 3 Part B (Boxes 8-17, 9.0 pts scaled)."""
    score = 0.0
    breakdown: Dict[str, float] = {}
    feedback: List[str] = []

    # Box 8: Stationary because no simulation time elapsed (0.9 pt)
    b8 = boxes.get(8, "").lower()
    if "time" in b8 or "stationary" in b8 or "elapsed" in b8:
        breakdown["Box 8"] = 0.9
        score += 0.9
    else:
        breakdown["Box 8"] = 0.0

    # Box 9: Constant velocity condition (0.9 pt)
    b9 = boxes.get(9, "").lower()
    if "constant" in b9 or "zero" in b9 or "net force" in b9:
        breakdown["Box 9"] = 0.9
        score += 0.9
    else:
        breakdown["Box 9"] = 0.0

    # Box 10: In-place assignment vs mathematical equality (0.9 pt)
    b10 = boxes.get(10, "").lower()
    if "agree" in b10 or "assignment" in b10 or "memory" in b10:
        breakdown["Box 10"] = 0.9
        score += 0.9
    else:
        breakdown["Box 10"] = 0.0

    # Box 11: Single time step too brief (0.9 pt)
    b11 = boxes.get(11, "").lower()
    if "single" in b11 or "tiny" in b11 or "step" in b11 or "stationary" in b11:
        breakdown["Box 11"] = 0.9
        score += 0.9
    else:
        breakdown["Box 11"] = 0.0

    # Box 12: Passes through wall (0.9 pt)
    b12 = boxes.get(12, "").lower()
    if "through" in b12 or "passes" in b12 or "northeast" in b12:
        breakdown["Box 12"] = 0.9
        score += 0.9
    else:
        breakdown["Box 12"] = 0.0

    # Box 13: Expected bounce (0.9 pt)
    b13 = boxes.get(13, "").lower()
    if "bounce" in b13 or "reverse" in b13 or "reflect" in b13:
        breakdown["Box 13"] = 0.9
        score += 0.9
    else:
        breakdown["Box 13"] = 0.0

    # Box 14: -v_x in x-axis (0.9 pt)
    b14 = boxes.get(14, "").lower()
    if "-v_x" in b14 or "-vx" in b14 or "reverse" in b14 or "opposite" in b14:
        breakdown["Box 14"] = 0.9
        score += 0.9
    else:
        breakdown["Box 14"] = 0.0

    # Box 15: Observation of 1D bounce (0.9 pt)
    b15 = boxes.get(15, "").lower()
    if "left" in b15 or "reverse" in b15 or "collid" in b15:
        breakdown["Box 15"] = 0.9
        score += 0.9
    else:
        breakdown["Box 15"] = 0.0

    # Box 16: 2D bounce + Newton's 3rd Law / normal force (0.9 pt)
    b16 = boxes.get(16, "").lower()
    if ("bounc" in b16 or "upward" in b16) and ("normal" in b16 or "3rd law" in b16 or "force" in b16 or "newton" in b16):
        breakdown["Box 16"] = 0.9
        score += 0.9
    else:
        breakdown["Box 16"] = 0.45
        score += 0.45

    # Box 17: Bouncing in all 4 walls (0.9 pt)
    b17 = boxes.get(17, "").lower()
    if "all" in b17 or "four" in b17 or "enclosure" in b17 or "reflect" in b17 or "box" in b17:
        breakdown["Box 17"] = 0.9
        score += 0.9
    else:
        breakdown["Box 17"] = 0.0

    return EvaluationResult(score=round(score, 2), max_score=9.0, breakdown=breakdown, feedback_lines=feedback)


def evaluate_lab3_final_code(code_str: str) -> EvaluationResult:
    """Evaluates Lab 3 Final Code (Trinket/VPython, 6.0 pts or 20.0 standalone)."""
    if not code_str.strip():
        return EvaluationResult(
            score=0.0,
            max_score=6.0,
            breakdown={
                "Scene Setup": 0.0, "Variables Setup": 0.0, "Animation Loop": 0.0,
                "Euler Integration": 0.0, "Collision Logic": 0.0
            },
            feedback_lines=["Code is empty."],
        )

    score = 0.0
    breakdown: Dict[str, float] = {}
    feedback: List[str] = []

    # 1. Objects setup: sphere and box (1.0 pt)
    if "sphere(" in code_str and "box(" in code_str:
        breakdown["Scene Setup"] = 1.0
        score += 1.0
    else:
        breakdown["Scene Setup"] = 0.5
        score += 0.5
        feedback.append("Define ball (sphere) and walls (box).")

    # 2. Velocity and timestep (1.0 pt)
    if "velocity" in code_str and ("deltat" in code_str or "dt" in code_str):
        breakdown["Variables Setup"] = 1.0
        score += 1.0
    else:
        breakdown["Variables Setup"] = 0.0

    # 3. Animation loop with rate() (1.0 pt)
    if "while" in code_str and "rate(" in code_str:
        breakdown["Animation Loop"] = 1.0
        score += 1.0
    else:
        breakdown["Animation Loop"] = 0.0
        feedback.append("Include rate() inside animation loop to avoid freezing.")

    # 4. Position update (1.0 pt)
    if "ball.pos" in code_str and "velocity" in code_str:
        breakdown["Euler Integration"] = 1.0
        score += 1.0
    else:
        breakdown["Euler Integration"] = 0.0

    # 5. Boundary collision reflections in X and Y (2.0 pts)
    bounce_x = "ball.velocity.x" in code_str and "-" in code_str
    bounce_y = "ball.velocity.y" in code_str and "-" in code_str
    b_score = 0.0
    if bounce_x:
        b_score += 1.0
    if bounce_y:
        b_score += 1.0
    breakdown["Collision Logic"] = b_score
    score += b_score
    if b_score < 2.0:
        feedback.append("Implement elastic boundary collisions in both horizontal and vertical axes.")

    return EvaluationResult(score=round(score, 2), max_score=6.0, breakdown=breakdown, feedback_lines=feedback)


# --- 4. Feedback Comment Generator ---

def generate_feedback_comment(result: EvaluationResult, assignment_name: str) -> str:
    """Builds structured itemized feedback comment for Canvas SpeedGrader."""
    lines = [
        f"[Automated Evaluation - PHYS1000 Lab Grading Agent]",
        f"Assignment: {assignment_name}",
        f"Total Score: {result.score:.1f} / {result.max_score:.1f}",
        "",
        "Itemized Rubric Breakdown:",
    ]
    for section, pts in result.breakdown.items():
        lines.append(f"  - {section}: {pts:.1f} pts")

    if result.penalties_applied:
        lines.append("")
        lines.append("Penalties Applied:")
        for pen, val in result.penalties_applied.items():
            lines.append(f"  - {pen}: -{val:.1f} pts")

    if result.feedback_lines:
        lines.append("")
        lines.append("Feedback & Constructive Notes:")
        for note in result.feedback_lines:
            lines.append(f"  * {note}")

    return "\n".join(lines)


# --- 5. High-Level REST API Posting Client ---

class CanvasGradingClient:
    """REST API Client for reading submissions and posting grades/comments."""

    def __init__(self, base_url: str, session: Optional[CanvasSession] = None):
        self.base_url = base_url.rstrip("/")
        self.session = session

    def _headers(self) -> Dict[str, str]:
        headers = {}
        if self.session:
            headers["Cookie"] = self.session.get_cookie_header()
            headers["X-CSRF-Token"] = self.session.csrf_token
        return headers

    def get_submission(self, assignment_id: int, user_id: int) -> RawSubmission:
        url = f"{self.base_url}/api/v1/courses/86326/assignments/{assignment_id}/submissions/{user_id}?include[]=submission_comments&include[]=user"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return RawSubmission(
            user_id=data["user_id"],
            assignment_id=data["assignment_id"],
            submission_type=data.get("submission_type"),
            body_html=data.get("body"),
            attachments=data.get("attachments", []),
            workflow_state=data.get("workflow_state", "unsubmitted"),
            score=data.get("score"),
        )

    def download_attachment(self, attachment_url: str) -> bytes:
        full_url = urljoin(self.base_url, attachment_url)
        resp = requests.get(full_url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.content

    def post_grade_and_comment(
        self,
        assignment_id: int,
        user_id: int,
        result: EvaluationResult,
        assignment_name: str = "Lab Assignment",
    ) -> SubmissionReceipt:
        comment_text = generate_feedback_comment(result, assignment_name)
        url = f"{self.base_url}/api/v1/courses/86326/assignments/{assignment_id}/submissions/{user_id}"
        payload = {
            "submission[posted_grade]": str(result.score),
            "comment[text_comment]": comment_text,
        }
        resp = requests.put(url, data=payload, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return SubmissionReceipt(
            status="graded",
            assignment_id=assignment_id,
            user_id=user_id,
            score=result.score,
            comment_posted=True,
        )
