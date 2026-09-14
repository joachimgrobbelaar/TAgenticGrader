"""Unit tests for the submission extractor module (Milestone 2).

Verifies PDF extraction (Exp05, Exp06), worksheet HTML parsing (Part A, Part B),
and VPython simulation code extraction (including Websnappr PNG snapshots).
"""

from __future__ import annotations

from src.extractor import (
    BaseExtractor,
    CodeExtractor,
    ExtractedCode,
    ExtractedPDFReport,
    ExtractedSubmission,
    ExtractedWorksheet,
    ParsedSubmission,
    RawSubmission,
    parse_exp05_pdf,
    parse_exp06_pdf,
    parse_lab3_html,
    parse_lab3_worksheet,
    parse_submission,
    parse_vpython_code,
)
from tests.mock_server import (
    REFERENCE_VPYTHON_CODE,
    create_exp05_pdf,
)


# ==============================================================================
# 1. Base Extractor & Data Models Tests
# ==============================================================================
class TestBaseExtractor:
    """Tests for BaseExtractor helper methods and data models."""

    def test_clean_text_normalizes_unicode_and_entities(self):
        raw = "alpha &plusmn; 0.05 &deg;C &#39;test&#39; 100 &minus; 20"
        cleaned = BaseExtractor.clean_text(raw)
        assert "+/-" in cleaned
        assert "'" in cleaned
        assert "-" in cleaned

    def test_parse_value_with_uncertainty(self):
        val, err = BaseExtractor.parse_value_with_uncertainty("6.1 +/- 0.05 cm")
        assert val == 6.1
        assert err == 0.05

        val2, err2 = BaseExtractor.parse_value_with_uncertainty("100.0 ± 0.05")
        assert val2 == 100.0
        assert err2 == 0.05

        val3, err3 = BaseExtractor.parse_value_with_uncertainty("12.0")
        assert val3 == 12.0
        assert err3 is None

        val4, err4 = BaseExtractor.parse_value_with_uncertainty("invalid")
        assert val4 is None
        assert err4 is None

    def test_data_model_type_compatibility(self):
        sub = ExtractedSubmission(assignment_type="exp05")
        assert isinstance(sub, ParsedSubmission)


# ==============================================================================
# 2. Experiment 05 PDF Extractor Tests
# ==============================================================================
class TestExp05PDFExtractor:
    """Tests for Exp05 Thermal Expansion PDF report extraction."""

    def test_extract_exp05_metadata(self, sample_exp05_pdf: bytes):
        report = parse_exp05_pdf(sample_exp05_pdf)
        assert isinstance(report, ExtractedPDFReport)
        assert report.student_name == "Sbongokuhle Mbizane"
        assert report.student_id == 156944
        assert report.group == "Fri2"
        assert report.page_count >= 2

    def test_extract_brass_table(self, sample_exp05_pdf: bytes):
        report = parse_exp05_pdf(sample_exp05_pdf)
        assert report.numerical_values["brass_d"] == 6.1
        assert report.uncertainties["brass_d"] == 0.05
        assert report.numerical_values["brass_a"] == 2.1
        assert report.numerical_values["brass_D"] == 100.0
        assert report.numerical_values["brass_l0"] == 51.0
        assert report.numerical_values["brass_T1"] == 16.0
        assert report.numerical_values["brass_T2"] == 88.0
        assert report.numerical_values["brass_delta_T"] == 72.0

        brass_tbl = report.tables.get("brass", {})
        assert "d" in brass_tbl
        assert brass_tbl["d"]["value"] == 6.1

    def test_extract_stainless_steel_table(self, sample_exp05_pdf: bytes):
        report = parse_exp05_pdf(sample_exp05_pdf)
        assert report.numerical_values["ss_d"] == 5.1
        assert report.uncertainties["ss_d"] == 0.05
        assert report.numerical_values["ss_a"] == 2.1
        assert report.numerical_values["ss_D"] == 100.0
        assert report.numerical_values["ss_l0"] == 51.0
        assert report.numerical_values["ss_T1"] == 18.0
        assert report.numerical_values["ss_T2"] == 90.0
        assert report.numerical_values["ss_delta_T"] == 72.0

    def test_extract_expansion_calculations(self, sample_exp05_pdf: bytes):
        report = parse_exp05_pdf(sample_exp05_pdf)
        calc_txt = report.text_sections.get("calculations", "")
        assert "Delta l = (a * d) / (2 * D)" in calc_txt
        assert "alpha" in calc_txt
        assert report.numerical_values.get("alpha_brass") == 17.44
        assert report.numerical_values.get("alpha_ss") == 14.60

    def test_extract_questions_q1_to_q3(self, sample_exp05_pdf: bytes):
        report = parse_exp05_pdf(sample_exp05_pdf)
        assert "2*theta" in report.text_sections["q1"] or "2 * D" in report.text_sections["q1"]
        assert "14%" in report.text_sections["q2"] or "6.1%" in report.text_sections["q2"]
        assert "stainless steel" in report.text_sections["q3"].lower()

    def test_detects_omitted_units(self):
        pdf_no_units = create_exp05_pdf(omit_units=True)
        report = parse_exp05_pdf(pdf_no_units)
        assert "units" in report.missing_elements

    def test_empty_pdf_handled(self):
        empty_doc = create_exp05_pdf(
            include_intro=False,
            include_objective=False,
            include_brass=False,
            include_ss=False,
            include_alpha=False,
            include_discussion=False,
            include_conclusion=False,
            include_q1=False,
            include_q2=False,
            include_q3=False,
        )
        report = parse_exp05_pdf(empty_doc)
        assert isinstance(report, ExtractedPDFReport)


# ==============================================================================
# 3. Experiment 06 PDF Extractor Tests
# ==============================================================================
class TestExp06PDFExtractor:
    """Tests for Exp06 Thin Lenses PDF report extraction."""

    def test_extract_method1_rough_estimate(self, sample_exp06_pdf: bytes):
        report = parse_exp06_pdf(sample_exp06_pdf)
        assert report.numerical_values["method1_v"] == 11.5
        assert report.uncertainties.get("method1_v") == 0.05

    def test_extract_method2_separation_data(self, sample_exp06_pdf: bytes):
        report = parse_exp06_pdf(sample_exp06_pdf)
        assert report.tables["method2_row_count"] == 6
        assert len(report.tables["method2_rows"]) == 6
        row0 = report.tables["method2_rows"][0]
        assert row0["s"] == 50.0
        assert row0["u1"] == 20.0
        assert row0["u2"] == 30.0
        assert row0["d"] == 10.0
        assert row0["d2_s"] == 2.00

    def test_extract_method2_intercept_and_focal_length(self, sample_exp06_pdf: bytes):
        report = parse_exp06_pdf(sample_exp06_pdf)
        assert report.numerical_values["method2_f"] == 12.0
        assert report.uncertainties.get("method2_f") == 0.1

    def test_extract_method3_statistics(self, sample_exp06_pdf: bytes):
        report = parse_exp06_pdf(sample_exp06_pdf)
        assert report.numerical_values["method3_mean_f"] == 12.0
        assert report.numerical_values["method3_sigma"] == 0.014
        assert len(report.tables["method3_rows"]) == 6

    def test_extract_questions(self, sample_exp06_pdf: bytes):
        report = parse_exp06_pdf(sample_exp06_pdf)
        assert "inverted" in report.text_sections["q1"].lower()
        assert "1/u" in report.text_sections["q2"] or "infinity" in report.text_sections["q2"].lower()
        assert "focal point" in report.text_sections["q3"].lower()


# ==============================================================================
# 4. Lab 3 Worksheet Extractor Tests
# ==============================================================================
class TestLab3WorksheetExtractor:
    """Tests for Lab 3 Part A & Part B online worksheet extraction."""

    def test_extract_part_a_boxes_1_to_7(self, sample_lab3_html_a: str):
        worksheet = parse_lab3_worksheet(sample_lab3_html_a)
        assert isinstance(worksheet, ExtractedWorksheet)
        assert worksheet.assignment_type == "part_a"
        assert worksheet.box_count == 7
        assert "straight line" in worksheet.get_box(1).lower()
        assert "r_f" in worksheet.get_box(2) and "v*t" in worksheet.get_box(2)
        assert "33" in worksheet.get_box(3)
        assert "-p_x" in worksheet.get_box(4)
        assert "closed" in worksheet.get_box(5).lower()
        assert "-p_x" in worksheet.get_box(6)
        assert "-p_y" in worksheet.get_box(7) or "- p_y" in worksheet.get_box(7)

    def test_extract_part_b_boxes_8_to_17(self, sample_lab3_html_b: str):
        worksheet = parse_lab3_worksheet(sample_lab3_html_b)
        assert worksheet.assignment_type == "part_b"
        assert worksheet.box_count == 10
        assert "stationary" in worksheet.get_box(8).lower()
        assert "constant" in worksheet.get_box(9).lower()
        assert "bounce" in worksheet.get_box(13).lower()
        assert "-v_x" in worksheet.get_box(14).lower()
        assert "all four walls" in worksheet.get_box(17).lower() or "enclosure" in worksheet.get_box(17).lower()

    def test_parse_boxes_with_case_and_formatting_variants(self):
        varied_html = """
        <div>
            <p><b>box 1:</b> Moving right</p>
            <p><b>Box 2</b>: r(t) = v*t</p>
            <p>BOX 3 - 33.0 mm</p>
            <p><b>Box 4:</b> -p_x</p>
        </div>
        """
        boxes = parse_lab3_html(varied_html)
        assert boxes[1] == "Moving right"
        assert boxes[2] == "r(t) = v*t"
        assert "33.0" in boxes[3]
        assert boxes[4] == "-p_x"


# ==============================================================================
# 5. Lab 3 Code Extractor Tests
# ==============================================================================
class TestLab3CodeExtractor:
    """Tests for Lab 3 VPython simulation code and Websnappr PNG extraction."""

    def test_extract_from_valid_source_code_string(self):
        code_res = parse_vpython_code(REFERENCE_VPYTHON_CODE)
        assert isinstance(code_res, ExtractedCode)
        assert code_res.syntax_valid is True
        assert code_res.has_scene is True
        assert code_res.has_objects is True
        assert code_res.has_velocity is True
        assert code_res.has_timestep is True
        assert code_res.has_rate is True
        assert code_res.has_loop is True
        assert code_res.has_euler_integration is True
        assert code_res.has_boundary_reflection is True
        assert len(code_res.missing_elements) == 0

    def test_extract_from_websnappr_png_bytes(self, sample_websnappr_png: bytes):
        extractor = CodeExtractor()
        code_res = extractor.extract(sample_websnappr_png)
        assert isinstance(code_res, ExtractedCode)
        assert code_res.has_objects is True
        assert code_res.has_rate is True
        assert code_res.has_boundary_reflection is True
        assert "sphere(" in code_res.source_code
        assert "box(" in code_res.source_code

    def test_extract_code_with_missing_rate(self):
        incomplete_code = """
from vpython import *
ball = sphere(pos=vector(0,0,0))
wall = box(pos=vector(10,0,0))
ball.velocity = vector(1,0,0)
deltat = 0.01
while True:
    ball.pos = ball.pos + ball.velocity * deltat
"""
        code_res = parse_vpython_code(incomplete_code)
        assert code_res.has_rate is False
        assert "rate() function" in code_res.missing_elements

    def test_extract_code_with_syntax_error(self):
        broken_code = "while True\n    ball.pos = ball.pos + 1"
        code_res = parse_vpython_code(broken_code)
        assert code_res.syntax_valid is False
        assert any("Syntax error" in w for w in code_res.extraction_warnings)

    def test_empty_code_submission(self):
        code_res = parse_vpython_code("")
        assert code_res.is_valid is False
        assert len(code_res.missing_elements) == 5


# ==============================================================================
# 6. Unified parse_submission Entrypoint Tests
# ==============================================================================
class TestUnifiedParseSubmission:
    """Tests for the polymorphic parse_submission dispatch interface."""

    def test_dispatch_exp05(self, sample_exp05_pdf: bytes):
        parsed = parse_submission(sample_exp05_pdf, assignment_type="exp05")
        assert isinstance(parsed, ExtractedPDFReport)
        assert parsed.assignment_type == "exp05"
        assert parsed.numerical_values["brass_d"] == 6.1

    def test_dispatch_exp06(self, sample_exp06_pdf: bytes):
        parsed = parse_submission(sample_exp06_pdf, assignment_type="exp06")
        assert isinstance(parsed, ExtractedPDFReport)
        assert parsed.assignment_type == "exp06"
        assert parsed.numerical_values["method1_v"] == 11.5

    def test_dispatch_lab3_part_a(self, sample_lab3_html_a: str):
        parsed = parse_submission(sample_lab3_html_a, assignment_type="lab3_part_a")
        assert isinstance(parsed, ExtractedWorksheet)
        assert parsed.assignment_type == "part_a"

    def test_dispatch_lab3_part_b(self, sample_lab3_html_b: str):
        parsed = parse_submission(sample_lab3_html_b, assignment_type="lab3_part_b")
        assert isinstance(parsed, ExtractedWorksheet)
        assert parsed.assignment_type == "part_b"

    def test_dispatch_lab3_final_code(self):
        parsed = parse_submission(REFERENCE_VPYTHON_CODE, assignment_type="lab3_final_code")
        assert isinstance(parsed, ExtractedCode)
        assert parsed.assignment_type == "lab3_final_code"

    def test_dispatch_auto_from_raw_submission(self, sample_exp05_pdf: bytes):
        raw = RawSubmission(
            user_id=156944,
            assignment_id=316697,
            submission_type="online_upload",
            attachments=[{"bytes": sample_exp05_pdf, "display_name": "report.pdf"}],
        )
        parsed = parse_submission(raw, assignment_type="auto")
        assert isinstance(parsed, ExtractedPDFReport)
        assert parsed.assignment_type == "exp05"
