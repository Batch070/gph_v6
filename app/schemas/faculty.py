"""Pydantic schemas for faculty-facing endpoints."""

from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


# ── Dashboard student row ─────────────────────────────────────
class StudentListItem(BaseModel):
    roll_no: str
    name: str
    branch: str
    semester: int
    academic_year: str
    dob: date
    ncc: bool
    hosteller: bool
    practical_attendance: float
    theory_attendance: float
    student_status: str
    request_id: Optional[int] = None
    request_status: Optional[str] = None
    request_note: Optional[str] = None

    model_config = {"from_attributes": True}


class FacultyDashboard(BaseModel):
    faculty_name: str
    faculty_role: str
    students: list[StudentListItem] = []


# ── Update request ────────────────────────────────────────────
class UpdateRequestPayload(BaseModel):
    status: str  # "Approved" or "Rejected"
    note: Optional[str] = None


class UpdateRequestResponse(BaseModel):
    message: str
    request_id: int
    new_status: str

class BulkUpdateRequestPayload(BaseModel):
    request_ids: list[int]
    status: str

class BulkUpdateRequestResponse(BaseModel):
    message: str
    updated_count: int
