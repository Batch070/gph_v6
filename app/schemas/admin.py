from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class OverviewResponse(BaseModel):
    total_fine_collected: float
    total_students: int
    total_branches: int
    total_semesters: int
    pending_requests: int

class BranchDataRow(BaseModel):
    department: str
    semester: str
    total_students: int
    total_fine_generated: float
    total_fine_collected: float
    defaulters: int

class BranchDataResponse(BaseModel):
    data: List[BranchDataRow]

class GlobalStudentRow(BaseModel):
    roll_no: str
    name: str
    department: str
    semester: int
    theory_attendance: float
    practical_attendance: float
    total_fine: float
    status: str

class GlobalStudentsResponse(BaseModel):
    students: List[GlobalStudentRow]

class FacultyMemberRow(BaseModel):
    id: int
    name: str
    department: str
    role: str
    username: str

class FacultyListResponse(BaseModel):
    faculty: List[FacultyMemberRow]

class AdminUpdateRoleBody(BaseModel):
    new_role: str

class AdminAddFacultyBody(BaseModel):
    name: str
    username: str
    password: str
    role: str
    department: Optional[str] = None
    gender: Optional[str] = None

class AdminGenericResponse(BaseModel):
    message: str

class AttendanceInsightRow(BaseModel):
    branch: str
    semester: int
    theory_avg: float
    practical_avg: float
    student_count: int

class AttendanceInsightsResponse(BaseModel):
    insights: List[AttendanceInsightRow]

class OverallStats(BaseModel):
    total_ncc: int
    total_hosteller: int
    total_pending: int
    total_accepted: int

class DBInsightRow(BaseModel):
    branch: str
    semester: int
    incharge_name: str
    total_students: int

class DBInsightsResponse(BaseModel):
    overall_stats: OverallStats
    insights: List[DBInsightRow]
