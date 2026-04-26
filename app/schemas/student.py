"""Pydantic schemas for student-facing endpoints."""

from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


# ── Dashboard ─────────────────────────────────────────────────
class StudentProfile(BaseModel):
    roll_no: str
    name: str
    branch: str
    semester: int
    academic_year: str
    dob: date
    gender: Optional[str] = None
    ncc: bool
    hosteller: bool

    model_config = {"from_attributes": True}


class AttendanceInfo(BaseModel):
    practical_attendance: float
    theory_attendance: float


class FineInfo(BaseModel):
    id: int
    amount: float
    semester: int
    status: str
    payment_date: Optional[datetime] = None
    transaction_id: Optional[str] = None

    model_config = {"from_attributes": True}


class ApprovalEntry(BaseModel):
    request_id: int
    faculty_name: str
    faculty_role: str
    status: str
    note: Optional[str] = None


class FineSummary(BaseModel):
    total_fine: float = 0.0
    paid: float = 0.0
    pending: float = 0.0
    fines: list[FineInfo] = []


class StudentDashboard(BaseModel):
    profile: StudentProfile
    profile_status: str = "Pending"
    attendance: AttendanceInfo
    hostel_superintendent: Optional[str] = None
    fine: Optional[FineInfo] = None
    fine_summary: Optional[FineSummary] = None
    approvals: list[ApprovalEntry] = []
    all_approved: bool = False
    can_pay: bool = False
    can_submit_request: bool = True


# ── Submit Request ────────────────────────────────────────────
class ClearanceRequestResponse(BaseModel):
    message: str
    requests_created: int


# ── Pay Fine (Razorpay) ───────────────────────────────────────
class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
