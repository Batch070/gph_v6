"""Attendance routes — image upload, subject management, aggregation, finalization."""

from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.schemas.auth import TokenData
from app.services import attendance_service
from app.utils.deps import require_role

router = APIRouter(tags=["Attendance"])

# ClassIncharge (and HOD for viewing)
_incharge_roles = Depends(require_role("ClassIncharge", "HOD"))

class StudentAttendanceUpdate(BaseModel):
    id: int
    roll_no: str
    student_name: str
    total_classes: int
    attended_classes: int

class SubjectUpdateRequest(BaseModel):
    students: List[StudentAttendanceUpdate]


class StudentAttendanceCreate(BaseModel):
    roll_no: str
    student_name: str
    attended_classes: int

class ManualAttendanceRequest(BaseModel):
    semester: int
    subject_name: str
    group_type: str
    total_classes: int
    students: List[StudentAttendanceCreate]


@router.post("/api/attendance/upload")
def upload_register_image(
    semester: int = Query(...),
    subject_name: str = Query(...),
    group_type: str = Query(...),
    total_classes: int = Query(...),
    file: UploadFile = File(...),
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """
    Upload register image, extract attendance via AI, and save valid students to database.
    """
    if not file.content_type.startswith("image/"):
        return {"error": "File provided is not an image."}

    return attendance_service.process_register_image(
        file, semester, subject_name, group_type, total_classes, int(user.sub), db
    )

@router.post("/api/attendance/submit-manual")
def submit_manual_attendance(
    payload: ManualAttendanceRequest,
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """Save manually entered attendance data directly to the database."""
    return attendance_service.process_manual_attendance(
        payload.semester,
        payload.subject_name,
        payload.group_type,
        payload.total_classes,
        payload.students,
        int(user.sub),
        db
    )


@router.get("/api/attendance/subjects/{semester}")
def get_subjects(
    semester: int,
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """List all uploaded subjects for a semester."""
    return attendance_service.get_uploaded_subjects(semester, int(user.sub), db)


@router.get("/api/attendance/subject-detail")
def get_subject_detail(
    semester: int = Query(...),
    subject_name: str = Query(...),
    group_type: str = Query(...),
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """Get individual student records for a specific subject."""
    return attendance_service.get_subject_detail(
        semester, subject_name, group_type, int(user.sub), db
    )


@router.delete("/api/attendance/subject")
def delete_subject(
    semester: int = Query(...),
    subject_name: str = Query(...),
    group_type: str = Query(...),
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """Delete all records for a specific subject."""
    return attendance_service.delete_subject(
        semester, subject_name, group_type, int(user.sub), db
    )


@router.put("/api/attendance/subject")
def update_subject_attendance(
    payload: SubjectUpdateRequest,
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """Update extracted student attendance records."""
    return attendance_service.update_subject_records(payload.students, int(user.sub), db)


@router.get("/api/attendance/summary/{semester}")
def get_student_summary(
    semester: int,
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """Get aggregated per-student attendance summary across all subjects."""
    return attendance_service.get_student_summary(semester, int(user.sub), db)


from fastapi import BackgroundTasks

@router.post("/api/attendance/finalize/{semester}")
def finalize_attendance(
    semester: int,
    background_tasks: BackgroundTasks,
    user: TokenData = _incharge_roles,
    db: Session = Depends(get_db),
):
    """Finalize attendance — calculate fines and update student records."""
    return attendance_service.finalize_attendance(semester, int(user.sub), db, background_tasks)
