from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.services import subject_service
from app.schemas.auth import TokenData
from app.utils.deps import require_role

router = APIRouter(tags=["Subjects"])

class SubjectBase(BaseModel):
    semester: int
    name: str
    group_type: str
    subject_code: Optional[str] = None
    label: Optional[str] = None
    branch: Optional[str] = None

class SubjectResponse(SubjectBase):
    id: int

    class Config:
        from_attributes = True

@router.get("/api/subjects", response_model=List[SubjectResponse])
def get_subjects(
    semester: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_role("ClassIncharge", "HOD", "Admin", "Student"))
):
    branch_filter = None
    if user.role != "Admin":
        branch_filter = user.branch
    return subject_service.get_subjects(db, semester, branch_filter)

@router.post("/api/subjects", response_model=SubjectResponse)
def create_subject(
    payload: SubjectBase,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_role("Admin", "ClassIncharge", "HOD"))
):
    branch = payload.branch
    if user.role != "Admin":
        branch = user.branch
        
    return subject_service.create_subject(
        db, 
        payload.semester, 
        payload.name, 
        payload.group_type, 
        payload.subject_code, 
        payload.label,
        branch
    )

@router.put("/api/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    payload: SubjectBase,
    db: Session = Depends(get_db),
    _user: TokenData = Depends(require_role("Admin", "ClassIncharge"))
):
    subject = subject_service.update_subject(db, subject_id, **payload.dict())
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@router.delete("/api/subjects/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    _user: TokenData = Depends(require_role("Admin", "ClassIncharge"))
):
    success = subject_service.delete_subject(db, subject_id)
    if not success:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"message": "Subject deleted"}

@router.post("/api/subjects/populate")
def populate_subjects(
    db: Session = Depends(get_db),
    _user: TokenData = Depends(require_role("Admin"))
):
    subject_service.populate_initial_subjects(db)
    return {"message": "Initial subjects populated"}
