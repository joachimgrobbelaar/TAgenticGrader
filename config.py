"""Configuration module for Ulwazi Canvas SpeedGrader Autonomous Grading Agent.

Defines target course, assignments, cohort boundaries, DOM selectors,
and file path discovery logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ==============================================================================
# Canvas LMS Core Configuration
# ==============================================================================
BASE_URL: str = os.environ.get("CANVAS_BASE_URL", "https://ulwazi.wits.ac.za")
COURSE_ID: int = int(os.environ.get("CANVAS_COURSE_ID", "86326"))

# Teaching Assistant Identity
TA_NAME: str = "Joachim Grobbelaar"
TA_USER_ID: int = 41165

# Browser automation mode (headed by default for real-time SpeedGrader observability)
HEADLESS: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "0").lower() in ("1", "true", "yes")


# ==============================================================================
# Assignment Metadata & Target Specifications
# ==============================================================================
@dataclass(frozen=True)
class AssignmentConfig:
    """Specification for an assignment within Canvas SpeedGrader."""

    id: int
    name: str
    points_possible: float
    submission_types: list[str]
    memo_path: str
    speedgrader_url: str


# Target Assignment IDs
EXP05_ASSIGNMENT_ID: int = 316697
EXP06_ASSIGNMENT_ID: int = 316844
LAB3_PART_A_ASSIGNMENT_ID: int = 315832
LAB3_PART_B_ASSIGNMENT_ID: int = 315833
LAB3_FINAL_CODE_ASSIGNMENT_ID: int = 315831

# Default Memo PDF Paths on local host
EXP05_MEMO_PATH: str = "/home/m/Downloads/Exp05 - Thermal Expansion - Memo v2.pdf"
EXP06_MEMO_PATH: str = "/home/m/Downloads/Exp06 - Thin Lenses - Memo.pdf"
LAB3_MEMO_PATH: str = "/home/m/Downloads/lab3_online_worksheet_memo.pdf"

ASSIGNMENTS: dict[int, AssignmentConfig] = {
    EXP05_ASSIGNMENT_ID: AssignmentConfig(
        id=EXP05_ASSIGNMENT_ID,
        name="EXP 05: Thermal Expansion - Group2's (Mon2-Fri2)",
        points_possible=20.0,
        submission_types=["online_upload"],
        memo_path=EXP05_MEMO_PATH,
        speedgrader_url=f"{BASE_URL}/courses/{COURSE_ID}/gradebook/speed_grader?assignment_id={EXP05_ASSIGNMENT_ID}",
    ),
    EXP06_ASSIGNMENT_ID: AssignmentConfig(
        id=EXP06_ASSIGNMENT_ID,
        name="EXP 06: Thin Spherical Lenses - Group2's (Mon2-Fri2)",
        points_possible=20.0,
        submission_types=["online_upload"],
        memo_path=EXP06_MEMO_PATH,
        speedgrader_url=f"{BASE_URL}/courses/{COURSE_ID}/gradebook/speed_grader?assignment_id={EXP06_ASSIGNMENT_ID}",
    ),
    LAB3_PART_A_ASSIGNMENT_ID: AssignmentConfig(
        id=LAB3_PART_A_ASSIGNMENT_ID,
        name="Computer Lab 3: worksheet Part A",
        points_possible=7.0,
        submission_types=["online_text_entry", "online_upload"],
        memo_path=LAB3_MEMO_PATH,
        speedgrader_url=f"{BASE_URL}/courses/{COURSE_ID}/gradebook/speed_grader?assignment_id={LAB3_PART_A_ASSIGNMENT_ID}",
    ),
    LAB3_PART_B_ASSIGNMENT_ID: AssignmentConfig(
        id=LAB3_PART_B_ASSIGNMENT_ID,
        name="Computer Lab 3: worksheet Part B",
        points_possible=9.0,
        submission_types=["online_text_entry", "online_upload"],
        memo_path=LAB3_MEMO_PATH,
        speedgrader_url=f"{BASE_URL}/courses/{COURSE_ID}/gradebook/speed_grader?assignment_id={LAB3_PART_B_ASSIGNMENT_ID}",
    ),
    LAB3_FINAL_CODE_ASSIGNMENT_ID: AssignmentConfig(
        id=LAB3_FINAL_CODE_ASSIGNMENT_ID,
        name="Computer Lab 3: Link to your final code.",
        points_possible=6.0,
        submission_types=["online_url"],
        memo_path=LAB3_MEMO_PATH,
        speedgrader_url=f"{BASE_URL}/courses/{COURSE_ID}/gradebook/speed_grader?assignment_id={LAB3_FINAL_CODE_ASSIGNMENT_ID}",
    ),
}


def get_assignment_config(assignment_id: int) -> AssignmentConfig:
    """Retrieve assignment configuration by assignment ID."""
    if assignment_id not in ASSIGNMENTS:
        raise KeyError(
            f"Unknown assignment ID {assignment_id}. Known IDs: {list(ASSIGNMENTS.keys())}"
        )
    return ASSIGNMENTS[assignment_id]


def get_speedgrader_url(
    course_id: int = COURSE_ID,
    assignment_id: int | None = None,
    student_id: int | None = None,
    base_url: str = BASE_URL,
) -> str:
    """Construct full SpeedGrader URL with optional student query param."""
    aid = assignment_id or EXP05_ASSIGNMENT_ID
    url = f"{base_url}/courses/{course_id}/gradebook/speed_grader?assignment_id={aid}"
    if student_id is not None:
        url += f"&student_id={student_id}"
    return url


# ==============================================================================
# Cohort Configuration: Fri2 (Indices 28-62)
# ==============================================================================
COHORT_GROUP_CATEGORY_ID: int = 20999
COHORT_GROUP_ID: int = 144689
COHORT_GROUP_NAME: str = "Fri2"

# 1-indexed student range allocated to Joachim Grobbelaar
COHORT_START_INDEX: int = 28
COHORT_END_INDEX: int = 62
COHORT_TOTAL_STUDENTS: int = 35

# First and last students in allocated range
COHORT_FIRST_STUDENT_ID: int = 156944  # Sbongokuhle Mbizane
COHORT_LAST_STUDENT_ID: int = 190138  # Dalitso Mpwesiwa


# ==============================================================================
# Browser Profile & Storage State Paths
# ==============================================================================
DEFAULT_STORAGE_STATE_PATH: str = os.environ.get(
    "CANVAS_STORAGE_STATE", "/tmp/canvas_storage_state.json"
)


def find_firefox_cookies_path() -> Path | None:
    """Auto-detect the active Firefox cookies.sqlite database file."""
    env_path = os.environ.get("CANVAS_COOKIES_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    search_dirs = [
        Path.home() / ".config" / "mozilla" / "firefox",
        Path.home() / ".mozilla" / "firefox",
    ]

    for base in search_dirs:
        if not base.is_dir():
            continue
        # Check default-release profile first
        for profile_dir in base.iterdir():
            if profile_dir.is_dir() and "default-release" in profile_dir.name:
                cookie_file = profile_dir / "cookies.sqlite"
                if cookie_file.is_file():
                    return cookie_file
        # Check any default profile
        for profile_dir in base.iterdir():
            if profile_dir.is_dir() and "default" in profile_dir.name:
                cookie_file = profile_dir / "cookies.sqlite"
                if cookie_file.is_file():
                    return cookie_file

    return None


# ==============================================================================
# SpeedGrader DOM Selectors
# ==============================================================================
@dataclass(frozen=True)
class SpeedGraderSelectors:
    """CSS selectors matching Canvas SpeedGrader DOM architecture."""

    # Navigation & Student Selection
    PREV_STUDENT_BUTTON: str = (
        'button#prev-student-button, button[data-testid="previous-student-button"]'
    )
    NEXT_STUDENT_BUTTON: str = (
        'button#next-student-button, button[data-testid="next-student-button"]'
    )
    STUDENT_SELECT_TRIGGER: str = (
        'button#Drilldown-Trigger___0, button[data-testid="student-select-trigger"]'
    )
    STUDENT_SELECT_MENU: str = "#students_selectmenu"
    SELECTED_STUDENT_NAME: str = 'span[data-testid="selected-student"]'
    CURRENT_STUDENT_INDEX: str = 'span[data-testid="current-student-index"]'
    GRADED_STUDENTS_COUNT: str = 'span[data-testid="graded-students-count"]'

    # Submission Viewport & Iframes
    SUBMISSION_IFRAME: str = 'iframe[name="submission-preview-iframe"]'
    SPEEDGRADER_IFRAME: str = "#speedgrader_iframe"
    ATTACHMENT_LINK: str = 'button[data-testid^="submission-attachment-link-"]'
    SUBMISSION_DOWNLOAD_LINK: str = (
        '.submission-file-download, a[data-testid="submission-download-link"]'
    )

    # Grading Form
    GRADE_INPUT: str = 'input[data-testid="grade-input"], #grading-box-extended'
    SUBMISSION_STATUS_SELECT: str = 'input[data-testid="assignment-submission-status-select"]'

    # Feedback Comments & Rich Content Editor
    RCE_IFRAME: str = 'iframe[id^="rce-"][id$="_ifr"]'
    TINYMCE_BODY: str = "body#tinymce"
    COMMENT_TEXTAREA: str = '#speedgrader_comment_textarea, textarea[data-testid^="rce-"]'
    COMMENT_SUBMIT_BUTTON: str = (
        'button#comment_submit_button, button[data-testid="submit-comment-button"]'
    )


SELECTORS = SpeedGraderSelectors()
