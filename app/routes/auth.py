"""Auth routes — student and faculty login."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student import Student
from app.models.faculty import Faculty
from app.schemas.auth import StudentLoginRequest, FacultyLoginRequest, Token
from app.utils.security import verify_password, create_access_token
from app.middleware.rate_limit import limiter

router = APIRouter(tags=["Auth"])


@router.post("/api/student/login", response_model=Token)
@limiter.limit("5/minute")
def student_login(
    request: FastAPIRequest,
    body: StudentLoginRequest,
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.roll_no == body.roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Password is the student's DOB in YYYY-MM-DD format
    try:
        input_dob = datetime.strptime(body.dob, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="DOB must be in YYYY-MM-DD format",
        )

    if student.dob != input_dob:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": student.roll_no, "role": "Student"})
    return Token(access_token=token)


@router.post("/api/faculty/login", response_model=Token)
@limiter.limit("5/minute")
def faculty_login(
    request: FastAPIRequest,
    body: FacultyLoginRequest,
    db: Session = Depends(get_db),
):
    faculty = db.query(Faculty).filter(Faculty.username == body.username).first()
    if not faculty:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(body.password, faculty.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(faculty.id), "role": faculty.role})
    return Token(access_token=token)
