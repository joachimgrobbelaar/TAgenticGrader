"""
Mock server package for Canvas LMS SpeedGrader testing.
"""

from .data import ASSIGNMENTS, CURRENT_USER, FRI2_COHORT_DATA, JOACHIM_COHORT
from .fixtures import (
    REFERENCE_VPYTHON_CODE,
    create_exp05_pdf,
    create_exp06_pdf,
    create_lab3_part_a_html,
    create_lab3_part_b_html,
    create_websnappr_png,
)
from .server import MockCanvasServer, mock_state

__all__ = [
    "ASSIGNMENTS",
    "CURRENT_USER",
    "FRI2_COHORT_DATA",
    "JOACHIM_COHORT",
    "create_exp05_pdf",
    "create_exp06_pdf",
    "create_lab3_part_a_html",
    "create_lab3_part_b_html",
    "create_websnappr_png",
    "REFERENCE_VPYTHON_CODE",
    "MockCanvasServer",
    "mock_state",
]
