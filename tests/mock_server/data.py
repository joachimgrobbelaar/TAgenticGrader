"""
Mock Canvas data structures for PHYS1000 Course 86326.
Contains assignments, user profile, and the Fri2 cohort (118 students, indices 28-62).
"""

from typing import Any, Dict, List

# Target Assignments
ASSIGNMENTS: Dict[int, Dict[str, Any]] = {
    316697: {
        "id": 316697,
        "name": "EXP 05: Thermal Expansion - Group2's (Mon2-Fri2)",
        "points_possible": 20.0,
        "grading_type": "points",
        "submission_types": ["online_upload"],
        "allowed_extensions": ["pdf"],
        "course_id": 86326,
    },
    316844: {
        "id": 316844,
        "name": "EXP 06: Thin Spherical Lenses - Group2's (Mon2-Fri2)",
        "points_possible": 20.0,
        "grading_type": "points",
        "submission_types": ["online_upload"],
        "allowed_extensions": ["pdf"],
        "course_id": 86326,
    },
    315832: {
        "id": 315832,
        "name": "Computer Lab 3: worksheet Part A",
        "points_possible": 7.0,
        "grading_type": "points",
        "submission_types": ["online_text_entry", "online_upload"],
        "allowed_extensions": [],
        "course_id": 86326,
    },
    315833: {
        "id": 315833,
        "name": "Computer Lab 3: worksheet Part B",
        "points_possible": 9.0,
        "grading_type": "points",
        "submission_types": ["online_text_entry", "online_upload"],
        "allowed_extensions": [],
        "course_id": 86326,
    },
    315831: {
        "id": 315831,
        "name": "Computer Lab 3: Link to your final code.",
        "points_possible": 6.0,
        "grading_type": "points",
        "submission_types": ["online_url"],
        "allowed_extensions": [],
        "course_id": 86326,
    },
}

# TA User Profile (Joachim Grobbelaar)
CURRENT_USER: Dict[str, Any] = {
    "id": 41165,
    "name": "Joachim Grobbelaar",
    "sortable_name": "Grobbelaar, Joachim",
    "short_name": "Joachim",
    "login_id": "joachim.grobbelaar@wits.ac.za",
    "email": "joachimgrobbelaar@gmail.com",
    "enrollments": [
        {
            "id": 991234,
            "course_id": 86326,
            "type": "TaEnrollment",
            "role": "TaEnrollment",
            "enrollment_state": "active",
            "limit_privileges_to_course_section": False,
        }
    ],
}

# Full Student Manifest for Fri2 (ID: 144689)
# Indices 28 to 62 are allocated to Joachim Grobbelaar (total: 35 students)
FRI2_COHORT_DATA: List[Dict[str, Any]] = [
    # Indices 0 to 27: Allocated to other TAs (Tawanda Dube)
    {"index": i, "id": 150000 + i, "name": f"Student {i:02d}", "sortable_name": f"Student, {i:02d}"}
    for i in range(28)
] + [
    # Indices 28 to 62: Exactly matching explorer_survey_3 / gradingallocationsLabs.png
    {"index": 28, "id": 156944, "name": "Sbongokuhle Mbizane", "sortable_name": "Mbizane, Sbongokuhle"},
    {"index": 29, "id": 192479, "name": "Imange Mdalana", "sortable_name": "Mdalana, Imange"},
    {"index": 30, "id": 190766, "name": "Siphiwe Mdluli", "sortable_name": "Mdluli, Siphiwe"},
    {"index": 31, "id": 190523, "name": "Laviwa Mduzulwana", "sortable_name": "Mduzulwana, Laviwa"},
    {"index": 32, "id": 162635, "name": "Khazimula Memela", "sortable_name": "Memela, Khazimula"},
    {"index": 33, "id": 191077, "name": "Sbongakonke Memela", "sortable_name": "Memela, Sbongakonke"},
    {"index": 34, "id": 191939, "name": "Rufaro Mhandu", "sortable_name": "Mhandu, Rufaro"},
    {"index": 35, "id": 193451, "name": "Isisipho Mhlakaza", "sortable_name": "Mhlakaza, Isisipho"},
    {"index": 36, "id": 192770, "name": "Karabo Mhlongo", "sortable_name": "Mhlongo, Karabo"},
    {"index": 37, "id": 190777, "name": "Ntlhari Mitileni", "sortable_name": "Mitileni, Ntlhari"},
    {"index": 38, "id": 191544, "name": "Tshepo Moagi", "sortable_name": "Moagi, Tshepo"},
    {"index": 39, "id": 193498, "name": "Tshegofatso Moatshe", "sortable_name": "Moatshe, Tshegofatso"},
    {"index": 40, "id": 191023, "name": "Mphumeleli Mocheko", "sortable_name": "Mocheko, Mphumeleli"},
    {"index": 41, "id": 194121, "name": "Letlhogonolo Modise", "sortable_name": "Modise, Letlhogonolo"},
    {"index": 42, "id": 190740, "name": "Koketso Mofokeng", "sortable_name": "Mofokeng, Koketso"},
    {"index": 43, "id": 193560, "name": "Refiloe Mogashoa", "sortable_name": "Mogashoa, Refiloe"},
    {"index": 44, "id": 190890, "name": "Tumelo Mogotsi", "sortable_name": "Mogotsi, Tumelo"},
    {"index": 45, "id": 191004, "name": "Tshedza Mohale", "sortable_name": "Mohale, Tshedza"},
    {"index": 46, "id": 192147, "name": "Ntsako Mojapelo", "sortable_name": "Mojapelo, Ntsako"},
    {"index": 47, "id": 194098, "name": "Boikano Mokgosi", "sortable_name": "Mokgosi, Boikano"},
    {"index": 48, "id": 193859, "name": "Kgolagano Mokgwamme", "sortable_name": "Mokgwamme, Kgolagano"},
    {"index": 49, "id": 191636, "name": "Thato Mokhethi", "sortable_name": "Mokhethi, Thato"},
    {"index": 50, "id": 191136, "name": "Omphile Mokotedi", "sortable_name": "Mokotedi, Omphile"},
    {"index": 51, "id": 192837, "name": "Omphile Molefe", "sortable_name": "Molefe, Omphile"},
    {"index": 52, "id": 191678, "name": "Phemelo Molete", "sortable_name": "Molete, Phemelo"},
    {"index": 53, "id": 191289, "name": "Luyanda Moloi", "sortable_name": "Moloi, Luyanda"},
    {"index": 54, "id": 190760, "name": "Rethabile Moloi", "sortable_name": "Moloi, Rethabile"},
    {"index": 55, "id": 193026, "name": "Thato Moloto", "sortable_name": "Moloto, Thato"},
    {"index": 56, "id": 193792, "name": "Motshedisi Mophuleng", "sortable_name": "Mophuleng, Motshedisi"},
    {"index": 57, "id": 192244, "name": "Bokang Motaung", "sortable_name": "Motaung, Bokang"},
    {"index": 58, "id": 190349, "name": "Mila Mpayipheli", "sortable_name": "Mpayipheli, Mila"},
    {"index": 59, "id": 192622, "name": "Gift Mphela", "sortable_name": "Mphela, Gift"},
    {"index": 60, "id": 189124, "name": "Thiathu Mphohoni", "sortable_name": "Mphohoni, Thiathu"},
    {"index": 61, "id": 192171, "name": "Paballo Mphuti", "sortable_name": "Mphuti, Paballo"},
    {"index": 62, "id": 190138, "name": "Dalitso Mpwesiwa", "sortable_name": "Mpwesiwa, Dalitso"},
] + [
    # Indices 63 to 117: Allocated to Carel Grobbelaar and Kwandakwesizwe Hadebe
    {"index": i, "id": 160000 + i, "name": f"Student {i:02d}", "sortable_name": f"Student, {i:02d}"}
    for i in range(63, 118)
]

# Quick lookup helper: Joachim's allocated cohort
JOACHIM_COHORT: List[Dict[str, Any]] = [
    s for s in FRI2_COHORT_DATA if 28 <= s["index"] <= 62
]
assert len(JOACHIM_COHORT) == 35, f"Expected 35 students, got {len(JOACHIM_COHORT)}"
