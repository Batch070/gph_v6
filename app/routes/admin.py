"""Admin route — upload fines from Excel."""

from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import TokenData
from app.schemas.fine import FineUploadResponse
from app.schemas.admin import (
    OverviewResponse, BranchDataResponse, GlobalStudentsResponse,
    FacultyListResponse, AdminUpdateRoleBody, AdminAddFacultyBody,
    AdminGenericResponse, AttendanceInsightsResponse, DBInsightsResponse,
    BranchListResponse, AdminAddBranchBody, AdminUpdateBranchHodBody
)
from app.services import admin_service
from app.utils.deps import require_role

router = APIRouter(tags=["Admin"])

_admin_only = Depends(require_role("Admin"))

@router.post("/api/admin/upload-fines", response_model=FineUploadResponse)
def upload_fines(
    file: UploadFile = File(...),
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db),
):
    return admin_service.upload_fines(file, db)

@router.get("/api/admin/overview", response_model=OverviewResponse)
def get_overview(
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_overview(db)

@router.get("/api/admin/branch-data", response_model=BranchDataResponse)
def get_branch_data(
    department: str = Query("all"),
    semester: str = Query("all"),
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_branch_data(department, semester, db)

@router.get("/api/admin/students", response_model=GlobalStudentsResponse)
def get_global_students(
    search: str = Query("", description="Search by name or roll no"),
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_global_students(search, db)

@router.get("/api/admin/faculty", response_model=FacultyListResponse)
def get_all_faculty(
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_all_faculty(db)

@router.post("/api/admin/faculty", response_model=AdminGenericResponse)
def add_faculty(
    body: AdminAddFacultyBody,
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.add_faculty(
        body.name, body.username, body.password, body.role, body.department, body.gender, db
    )

@router.put("/api/admin/faculty/{target_id}/role", response_model=AdminGenericResponse)
def update_faculty_role(
    target_id: int,
    body: AdminUpdateRoleBody,
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.update_faculty_role(target_id, body.new_role, db)

@router.delete("/api/admin/faculty/{target_id}", response_model=AdminGenericResponse)
def delete_faculty(
    target_id: int,
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.delete_faculty(target_id, db)

@router.post("/api/admin/upload-admit-cards", response_model=AdminGenericResponse)
def upload_admit_cards(
    file: UploadFile = File(...),
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.upload_admit_cards(file, db)

@router.post("/api/admin/reset", response_model=AdminGenericResponse)
def reset_system(
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.reset_system(db)

@router.get("/api/admin/attendance-insights", response_model=AttendanceInsightsResponse)
def get_attendance_insights(
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_attendance_insights(db)

@router.get("/api/admin/db-insights", response_model=DBInsightsResponse)
def get_db_insights(
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_db_insights(db)

@router.get("/api/admin/branches", response_model=BranchListResponse)
def get_branches(
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.get_branches(db)

@router.post("/api/admin/branches", response_model=AdminGenericResponse)
def add_branch(
    body: AdminAddBranchBody,
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.add_branch_with_hod(
        body.name, body.hod_name, body.hod_username, body.hod_password, body.hod_gender, db
    )

@router.put("/api/admin/branches/{branch_name}/hod", response_model=AdminGenericResponse)
def update_branch_hod(
    branch_name: str,
    body: AdminUpdateBranchHodBody,
    _user: TokenData = _admin_only,
    db: Session = Depends(get_db)
):
    return admin_service.update_branch_hod(
        branch_name, body.hod_name, body.hod_username, body.hod_password, db
    )
