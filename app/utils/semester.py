from datetime import datetime
from typing import List


def get_active_semesters() -> List[int]:
    """
    Returns active semesters based on current month.
    - Jan (1) to June (6): Even Semesters [2, 4, 6]
    - August (8) to December (12): Odd Semesters [1, 3, 5]
    - July (7): Both or transition (Returning all for now)
    """
    month = datetime.now().month

    if 1 <= month <= 6:
        return [2, 4, 6]
    elif 8 <= month <= 12:
        return [1, 3, 5]
    else:
        # July or unexpected
        return [1, 2, 3, 4, 5, 6]


def is_semester_active(semester: int) -> bool:
    """Checks if a given semester is active based on the current date."""
    return semester in get_active_semesters()


def get_hod_semesters(branch: str) -> List[int]:
    """
    Returns the semesters managed by an HOD based on their branch.
    - First Year HOD: semesters 1 & 2 (all branches)
    - Department HODs: semesters 3, 4, 5, 6 (their branch only)
    """
    if branch == "First Year":
        return [1, 2]
    return [3, 4, 5, 6]


def get_active_hod_semesters(branch: str) -> List[int]:
    """
    Returns the intersection of active semesters and HOD-managed semesters.
    E.g. in May (even active): First Year HOD -> [2], Dept HOD -> [4, 6]
    """
    active = get_active_semesters()
    hod_sems = get_hod_semesters(branch)
    return [s for s in hod_sems if s in active]
