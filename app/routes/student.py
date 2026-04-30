"""Student routes — dashboard, submit-request, pay-fine, receipt."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import TokenData
from app.schemas.student import (
    StudentDashboard,
    ClearanceRequestResponse,
    RazorpayOrderResponse,
    PaymentVerificationRequest,
)
from app.services import student_service
from app.utils.deps import require_role

router = APIRouter(tags=["Student"])

_student_only = Depends(require_role("Student"))


@router.get("/api/student/dashboard", response_model=StudentDashboard)
def dashboard(
    user: TokenData = _student_only,
    db: Session = Depends(get_db),
):
    return student_service.get_dashboard(user.sub, db)


@router.post("/api/student/submit-request", response_model=ClearanceRequestResponse)
def submit_request(
    user: TokenData = _student_only,
    db: Session = Depends(get_db),
):
    return student_service.submit_clearance_request(user.sub, db)


@router.post("/api/student/create-razorpay-order", response_model=RazorpayOrderResponse)
def create_razorpay_order(
    user: TokenData = _student_only,
    db: Session = Depends(get_db),
):
    return student_service.create_razorpay_order(user.sub, db)


@router.get("/api/student/receipt", response_class=HTMLResponse)
def get_receipt(
    user: TokenData = _student_only,
    db: Session = Depends(get_db),
):
    """Generate and return a printable HTML payment receipt."""
    return student_service.generate_receipt(user.sub, db)


@router.post("/api/student/verify-payment")
def verify_payment(
    data: PaymentVerificationRequest,
    user: TokenData = _student_only,
    db: Session = Depends(get_db),
):
    return student_service.verify_payment(user.sub, data, db)
