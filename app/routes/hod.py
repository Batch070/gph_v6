"""HOD routes — overview, semesters, students, faculty CRUD, uploads, reports."""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import TokenData
from app.services import hod_service
from app.utils.deps import require_role

router = APIRouter(tags=["HOD"])

_hod_only = Depends(require_role("HOD"))


# ── Request Bodies ────────────────────────────────────────────
class AddFacultyBody(BaseModel):
    name: str
    username: str
    password: str
    role: str
    gender: Optional[str] = None


class UpdateRoleBody(BaseModel):
    new_role: str


class AssignInchargeBody(BaseModel):
    faculty_id: int
    semester: int


# ── Routes ────────────────────────────────────────────────────

@router.get("/api/hod/overview")
def hod_overview(
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_overview(int(user.sub), db)


@router.get("/api/hod/semesters")
def hod_semesters(
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_semesters(int(user.sub), db)


@router.get("/api/hod/students")
def hod_students(
    semester: Optional[int] = Query(None, description="Filter by semester"),
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_students(int(user.sub), semester, db)


@router.get("/api/hod/student/{roll_no}")
def hod_student_profile(
    roll_no: str,
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_student_profile(int(user.sub), roll_no, db)


@router.get("/api/hod/faculty")
def hod_faculty_list(
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_faculty_list(int(user.sub), db)


@router.post("/api/hod/faculty")
def hod_add_faculty(
    body: AddFacultyBody,
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.add_faculty(
        int(user.sub), body.name, body.username, body.password, body.role, body.gender, db
    )


@router.put("/api/hod/faculty/{target_id}/role")
def hod_update_faculty_role(
    target_id: int,
    body: UpdateRoleBody,
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.update_faculty_role(int(user.sub), target_id, body.new_role, db)


@router.delete("/api/hod/faculty/{target_id}")
def hod_remove_faculty(
    target_id: int,
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.remove_faculty(int(user.sub), target_id, db)


@router.post("/api/hod/faculty/assign-incharge")
def hod_assign_incharge(
    body: AssignInchargeBody,
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.assign_class_incharge(
        int(user.sub), body.faculty_id, body.semester, db
    )


@router.post("/api/hod/upload-branch")
def hod_upload_branch(
    file: UploadFile = File(...),
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.upload_branch_data(file, int(user.sub), db)


@router.post("/api/hod/upload-semester")
def hod_upload_semester(
    file: UploadFile = File(...),
    semester: int = Query(..., description="Target semester"),
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.upload_semester_data(file, semester, int(user.sub), db)


@router.get("/api/hod/reports")
def hod_reports(
    report_type: str = Query(..., description="collection or defaulter"),
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_report(int(user.sub), report_type, db)


@router.post("/api/hod/reset")
def hod_reset_data(
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.reset_data(int(user.sub), db)

@router.delete("/api/hod/semester/{semester}")
def hod_delete_semester(
    semester: int,
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.delete_semester_data(int(user.sub), semester, db)

@router.get("/api/hod/db-insights")
def hod_db_insights(
    user: TokenData = _hod_only,
    db: Session = Depends(get_db),
):
    return hod_service.get_db_insights(int(user.sub), db)
