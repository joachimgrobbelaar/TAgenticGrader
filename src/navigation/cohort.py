"""Cohort configuration and filtering module.

Manages student allocation for TA Joachim Grobbelaar on Group Fri2 (ID: 144689),
specifically allocated indices 28 to 62 (35 students total, user IDs 156944 to 190138).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import (
    COHORT_END_INDEX,
    COHORT_START_INDEX,
)


@dataclass(frozen=True)
class CohortStudent:
    """Represents an individual student in the allocated grading cohort."""

    index: int
    user_id: int
    name: str
    sortable_name: str


# Official TA student allocation roster for Fri2 28-62 from institutional matrix
FRI2_ALLOCATED_STUDENTS: list[CohortStudent] = [
    CohortStudent(28, 156944, "Sbongokuhle Mbizane", "Mbizane, Sbongokuhle"),
    CohortStudent(29, 192479, "Imange Mdalana", "Mdalana, Imange"),
    CohortStudent(30, 190766, "Siphiwe Mdluli", "Mdluli, Siphiwe"),
    CohortStudent(31, 190523, "Laviwa Mduzulwana", "Mduzulwana, Laviwa"),
    CohortStudent(32, 162635, "Khazimula Memela", "Memela, Khazimula"),
    CohortStudent(33, 191077, "Sbongakonke Memela", "Memela, Sbongakonke"),
    CohortStudent(34, 191939, "Rufaro Mhandu", "Mhandu, Rufaro"),
    CohortStudent(35, 193451, "Isisipho Mhlakaza", "Mhlakaza, Isisipho"),
    CohortStudent(36, 192770, "Karabo Mhlongo", "Mhlongo, Karabo"),
    CohortStudent(37, 190777, "Ntlhari Mitileni", "Mitileni, Ntlhari"),
    CohortStudent(38, 191544, "Tshepo Moagi", "Moagi, Tshepo"),
    CohortStudent(39, 193498, "Tshegofatso Moatshe", "Moatshe, Tshegofatso"),
    CohortStudent(40, 191023, "Mphumeleli Mocheko", "Mocheko, Mphumeleli"),
    CohortStudent(41, 194121, "Letlhogonolo Modise", "Modise, Letlhogonolo"),
    CohortStudent(42, 190740, "Koketso Mofokeng", "Mofokeng, Koketso"),
    CohortStudent(43, 193560, "Refiloe Mogashoa", "Mogashoa, Refiloe"),
    CohortStudent(44, 190890, "Tumelo Mogotsi", "Mogotsi, Tumelo"),
    CohortStudent(45, 191004, "Tshedza Mohale", "Mohale, Tshedza"),
    CohortStudent(46, 192147, "Ntsako Mojapelo", "Mojapelo, Ntsako"),
    CohortStudent(47, 194098, "Boikano Mokgosi", "Mokgosi, Boikano"),
    CohortStudent(48, 193859, "Kgolagano Mokgwamme", "Mokgwamme, Kgolagano"),
    CohortStudent(49, 191636, "Thato Mokhethi", "Mokhethi, Thato"),
    CohortStudent(50, 191136, "Omphile Mokotedi", "Mokotedi, Omphile"),
    CohortStudent(51, 192837, "Omphile Molefe", "Molefe, Omphile"),
    CohortStudent(52, 191678, "Phemelo Molete", "Molete, Phemelo"),
    CohortStudent(53, 191289, "Luyanda Moloi", "Moloi, Luyanda"),
    CohortStudent(54, 190760, "Rethabile Moloi", "Moloi, Rethabile"),
    CohortStudent(55, 193026, "Thato Moloto", "Moloto, Thato"),
    CohortStudent(56, 193792, "Motshedisi Mophuleng", "Mophuleng, Motshedisi"),
    CohortStudent(57, 192244, "Bokang Motaung", "Motaung, Bokang"),
    CohortStudent(58, 190349, "Mila Mpayipheli", "Mpayipheli, Mila"),
    CohortStudent(59, 192622, "Gift Mphela", "Mphela, Gift"),
    CohortStudent(60, 189124, "Thiathu Mphohoni", "Mphohoni, Thiathu"),
    CohortStudent(61, 192171, "Paballo Mphuti", "Mphuti, Paballo"),
    CohortStudent(62, 190138, "Dalitso Mpwesiwa", "Mpwesiwa, Dalitso"),
]

# Quick lookup indexes
_COHORT_BY_ID: dict[int, CohortStudent] = {s.user_id: s for s in FRI2_ALLOCATED_STUDENTS}
_COHORT_BY_INDEX: dict[int, CohortStudent] = {s.index: s for s in FRI2_ALLOCATED_STUDENTS}
_COHORT_USER_IDS: set[int] = set(_COHORT_BY_ID.keys())


def get_allocated_cohort() -> list[CohortStudent]:
    """Return the official list of 35 students allocated to Joachim Grobbelaar."""
    return list(FRI2_ALLOCATED_STUDENTS)


def get_cohort_user_ids() -> set[int]:
    """Return the set of Canvas user IDs in the allocated cohort."""
    return set(_COHORT_USER_IDS)


def is_cohort_student(user_id: int) -> bool:
    """Return True if user_id belongs to the allocated cohort."""
    return user_id in _COHORT_USER_IDS


def get_student_by_index(index: int) -> CohortStudent | None:
    """Find cohort student by 1-indexed position (28 to 62)."""
    return _COHORT_BY_INDEX.get(index)


def get_student_by_id(user_id: int) -> CohortStudent | None:
    """Find cohort student by Canvas user ID."""
    return _COHORT_BY_ID.get(user_id)


def filter_cohort_students(
    all_group_users: list[dict[str, Any]],
    start_idx: int = COHORT_START_INDEX,
    end_idx: int = COHORT_END_INDEX,
    sort_by_sortable_name: bool = True,
) -> list[dict[str, Any]]:
    """Filter group users down to the allocated student range (28 to 62).

    Supports:
    1. Datasets with explicit 'index' attributes (e.g. test fixtures).
    2. Canvas LMS user records matching known cohort user IDs (156944 to 190138).
    3. Positional roster slicing [start_idx - 1 : end_idx] on full group rosters.
    """
    if not all_group_users:
        return []

    # 1. If records carry an explicit 'index' field (as in mock datasets)
    has_indices = any("index" in u for u in all_group_users)
    if has_indices:
        matching = [
            dict(u, cohort_index=u.get("index", 0))
            for u in all_group_users
            if start_idx <= u.get("index", -1) <= end_idx
        ]
        matching.sort(key=lambda u: u.get("cohort_index", 0))
        if matching:
            return matching

    # 2. Check if users match known cohort user IDs (exact TA allocation)
    cohort_matches = [
        dict(u, cohort_index=_COHORT_BY_ID[u["id"]].index)
        for u in all_group_users
        if u.get("id") in _COHORT_USER_IDS
    ]
    if len(cohort_matches) == (end_idx - start_idx + 1):
        cohort_matches.sort(key=lambda u: u.get("cohort_index", 0))
        return cohort_matches

    # 3. Fallback to positional slicing if full group roster is provided
    if len(all_group_users) >= end_idx:
        sorted_users = list(all_group_users)
        if sort_by_sortable_name:
            sorted_users.sort(key=lambda u: (u.get("sortable_name") or u.get("name", "")).lower())
        sliced = sorted_users[start_idx - 1 : end_idx]
        result = []
        for idx, u in enumerate(sliced, start=start_idx):
            item = dict(u)
            item["cohort_index"] = idx
            result.append(item)
        return result

    # 4. Filter any partial subset matching cohort IDs
    if cohort_matches:
        cohort_matches.sort(key=lambda u: u.get("cohort_index", 0))
        return cohort_matches

    return []
