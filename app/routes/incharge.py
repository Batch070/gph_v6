"""Class Incharge routes — dashboard, upload fines, reports, reset."""

from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import TokenData
from app.schemas.fine import FineUploadResponse
from app.services import incharge_service, admin_service
from app.utils.deps import require_role

router = APIRouter(tags=["ClassIncharge"])

_incharge_only = Depends(require_role("ClassIncharge"))


@router.get("/api/incharge/overview")
def overview(
    user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return incharge_service.get_overview(int(user.sub), db)


@router.get("/api/incharge/semesters")
def semesters(
    user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return incharge_service.get_semesters(int(user.sub), db)


@router.get("/api/incharge/students")
def students(
    semester: Optional[int] = Query(None),
    user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return incharge_service.get_students(int(user.sub), semester, db)


@router.get("/api/incharge/student/{roll_no}")
def student_profile(
    roll_no: str,
    user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return incharge_service.get_student_profile(int(user.sub), roll_no, db)


@router.post("/api/incharge/upload-fines", response_model=FineUploadResponse)
def upload_fines(
    file: UploadFile = File(...),
    _user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return admin_service.upload_fines(file, db)


@router.get("/api/incharge/reports")
def reports(
    report_type: str = Query("paid", description="paid, unpaid, or monthly"),
    user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return incharge_service.get_report(int(user.sub), report_type, db)


@router.post("/api/incharge/reset")
def reset_data(
    user: TokenData = _incharge_only,
    db: Session = Depends(get_db),
):
    return incharge_service.reset_data(int(user.sub), db)
