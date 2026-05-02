"""Business logic for student-facing endpoints."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse

from app.models.student import Student
from app.models.faculty import Faculty
from app.models.request import Request
from app.models.fine import Fine
from app.schemas.student import (
    StudentDashboard,
    StudentProfile,
    AttendanceInfo,
    FineInfo,
    FineSummary,
    ApprovalEntry,
    ClearanceRequestResponse,
    RazorpayOrderResponse,
    PaymentVerificationRequest,
)
import razorpay
from app.config import settings

# Roles that EVERY student must get clearance from
_MANDATORY_ROLES = ["ClassIncharge", "PTI", "Librarian", "CanteenOwner", "HOD"]


def get_dashboard(roll_no: str, db: Session) -> StudentDashboard:
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")

    profile = StudentProfile.model_validate(student)
    attendance = AttendanceInfo(
        practical_attendance=student.practical_attendance or 0.0,
        theory_attendance=student.theory_attendance or 0.0,
    )

    # Current-semester fine (for backward compatibility)
    fine_row = (
        db.query(Fine)
        .filter(Fine.roll_no == roll_no, Fine.semester == student.semester)
        .first()
    )
    fine = FineInfo.model_validate(fine_row) if fine_row else None

    # Aggregated fine summary across all semesters
    all_fines = db.query(Fine).filter(Fine.roll_no == roll_no).all()
    fine_info_list = [FineInfo.model_validate(f) for f in all_fines]
    total_fine = sum(f.amount for f in all_fines)
    paid_amount = sum(f.amount for f in all_fines if f.status == "Paid")
    pending_amount = sum(f.amount for f in all_fines if f.status == "Unpaid")
    fine_summary = FineSummary(
        total_fine=total_fine,
        paid=paid_amount,
        pending=pending_amount,
        fines=fine_info_list,
    )

    # Find Hostel Superintendent name if hosteller
    hostel_sup_name = None
    has_hostel_sup_request = False
    required_sup_role = None
    if student.hosteller:
        is_male = student.gender in ["Boy", "Male"]
        required_sup_role = "HostelSuperintendent_Boys" if is_male else "HostelSuperintendent_Girls"
        sup = db.query(Faculty).filter(Faculty.role == required_sup_role).first()
        if sup:
            honorific = "Mrs. " if sup.gender == "Female" else "Mr. "
            hostel_sup_name = f"{honorific}{sup.name}"

    # Approval status per request
    requests = db.query(Request).filter(Request.roll_no == roll_no).all()
    approvals: list[ApprovalEntry] = []
    for req in requests:
        faculty = db.query(Faculty).filter(Faculty.id == req.faculty_id).first()
        if faculty and faculty.role == required_sup_role:
            has_hostel_sup_request = True

        faculty_name = "Unknown"
        if faculty:
            honorific = "Mrs. " if faculty.gender == "Female" else "Mr. "
            faculty_name = f"{honorific}{faculty.name}"

        approvals.append(
            ApprovalEntry(
                request_id=req.id,
                faculty_name=faculty_name,
                faculty_role=faculty.role if faculty else "Unknown",
                status=req.status,
                note=req.note,
            )
        )

    all_approved = bool(approvals) and all(a.status == "Approved" for a in approvals)

    # If hosteller, MUST have a superintendent request and it MUST be approved
    if student.hosteller and not has_hostel_sup_request:
        all_approved = False

    can_pay = all_approved and fine is not None and fine.status == "Unpaid"
    
    # A student can only submit requests if their fine and attendance data has been uploaded
    # by the administration for their current semester.
    has_fine = fine is not None
    has_attendance = student.theory_attendance > 0 or student.practical_attendance > 0
    can_submit = has_fine and has_attendance

    return StudentDashboard(
        profile=profile,
        profile_status=student.status or "Pending",
        attendance=attendance,
        hostel_superintendent=hostel_sup_name,
        fine=fine,
        fine_summary=fine_summary,
        approvals=approvals,
        all_approved=all_approved,
        can_pay=can_pay,
        can_submit_request=can_submit,
    )


def submit_clearance_request(roll_no: str, db: Session) -> ClearanceRequestResponse:
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Check if fine and attendance data are uploaded
    fine = (
        db.query(Fine)
        .filter(Fine.roll_no == roll_no, Fine.semester == student.semester)
        .first()
    )
    if not fine or (student.theory_attendance <= 0 and student.practical_attendance <= 0):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Fines and attendance data must be uploaded by the administration before submitting clearance requests.",
        )

    # Check for existing requests to avoid duplicates
    existing = db.query(Request).filter(Request.roll_no == roll_no).count()
    if existing > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Clearance requests already submitted",
        )

    roles_needed = list(_MANDATORY_ROLES)
    if student.ncc:
        roles_needed.append("ANO")
    
    created = 0
    # Process mandatory and optional (NCC) roles
    for role in roles_needed:
        if role == "HOD":
            if student.semester in [1, 2]:
                # First Year HOD (Manages Sems 1 & 2 for all branches)
                faculty = db.query(Faculty).filter(Faculty.role == "HOD", Faculty.branch == "First Year").first()
            else:
                # Departmental HOD (Manages Sems 3, 4, 5, 6 for specific branch)
                faculty = db.query(Faculty).filter(Faculty.role == "HOD", Faculty.branch == student.branch).first()
        else:
            faculty = (
                db.query(Faculty)
                .filter(Faculty.role == role, Faculty.branch == student.branch)
                .first()
            )
            if not faculty:
                # Fallback for roles like Librarian or CanteenOwner that might not be branch-specific
                faculty = db.query(Faculty).filter(Faculty.role == role).first()
        
        if faculty:
            req = Request(
                roll_no=roll_no,
                faculty_id=faculty.id,
                status="Pending",
                request_date=datetime.now(timezone.utc),
            )
            db.add(req)
            created += 1

    # Special handling for Hostellers
    if student.hosteller:
        is_male = student.gender in ["Boy", "Male"]
        sup_role = "HostelSuperintendent_Boys" if is_male else "HostelSuperintendent_Girls"
        
        sup = db.query(Faculty).filter(Faculty.role == sup_role).first()
        if sup:
            req = Request(
                roll_no=roll_no,
                faculty_id=sup.id,
                status="Pending",
                request_date=datetime.now(timezone.utc),
            )
            db.add(req)
            created += 1

    # Update student status
    student.status = "Pending"
    db.commit()

    return ClearanceRequestResponse(
        message="Clearance requests submitted successfully",
        requests_created=created,
    )


def create_razorpay_order(roll_no: str, db: Session) -> RazorpayOrderResponse:
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")

    # All requests must be approved
    requests = db.query(Request).filter(Request.roll_no == roll_no).all()
    if not requests:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No clearance requests found. Submit requests first.",
        )
    non_approved = [r for r in requests if r.status != "Approved"]
    if non_approved:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="All clearance requests must be approved before payment.",
        )

    fine = (
        db.query(Fine)
        .filter(Fine.roll_no == roll_no, Fine.semester == student.semester)
        .first()
    )
    if not fine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No fine record found")
    if fine.status == "Paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Fine already paid")

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Razorpay not configured")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    # Razorpay amount is in paise (₹1 = 100 paise)
    amount_in_paise = int(fine.amount * 100)
    
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"receipt_{fine.id}",
        "notes": {
            "roll_no": student.roll_no,
            "fine_id": fine.id
        }
    }
    
    try:
        order = client.order.create(data=order_data)
        return RazorpayOrderResponse(
            order_id=order["id"],
            amount=order["amount"],
            currency=order["currency"],
            key_id=settings.RAZORPAY_KEY_ID
        )
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create order: {str(e)}")


def generate_receipt(roll_no: str, db: Session) -> HTMLResponse:
    """Generate a downloadable HTML receipt for a paid fine."""
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")

    fine = (
        db.query(Fine)
        .filter(Fine.roll_no == roll_no, Fine.semester == student.semester, Fine.status == "Paid")
        .first()
    )
    if not fine:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No paid fine record found. Payment must be completed first.",
        )

    # Gather all approval info
    requests = db.query(Request).filter(Request.roll_no == roll_no).all()
    clearance_rows = ""
    for req in requests:
        faculty = db.query(Faculty).filter(Faculty.id == req.faculty_id).first()
        role = faculty.role if faculty else "Unknown"
        name = faculty.name if faculty else "Unknown"
        role_label = {
            'ClassIncharge': 'Class Incharge',
            'HOD': 'HOD',
            'PTI': 'PTI',
            'ANO': 'ANO (NCC)',
            'Librarian': 'Library',
            'CanteenOwner': 'Canteen',
            'HostelSuperintendent_Boys': 'Hostel Sup. (Boys)',
            'HostelSuperintendent_Girls': 'Hostel Sup. (Girls)',
        }.get(role, role)

        status_color = "#15803d" if req.status == "Approved" else "#b91c1c"
        clearance_rows += f"""
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;">{role_label}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;">{name}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;color:{status_color};font-weight:600;">{req.status}</td>
        </tr>"""

    payment_date_str = ""
    if fine.payment_date:
        payment_date_str = fine.payment_date.strftime("%d %b %Y, %I:%M %p")
    else:
        payment_date_str = datetime.now().strftime("%d %b %Y, %I:%M %p")

    receipt_no = f"GPH-{fine.id:06d}"

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Receipt — {receipt_no}</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Outfit', sans-serif; background: #f1f5f9; padding: 20px; color: #334155; }}
        .receipt-container {{
            max-width: 700px; margin: 0 auto; background: #fff;
            border-radius: 16px; overflow: hidden;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
        }}
        .receipt-header {{
            background: linear-gradient(135deg, #1e3a8a 0%, #2c4c9e 100%);
            color: white; padding: 32px 30px; text-align: center;
        }}
        .receipt-header h1 {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
        .receipt-header p {{ font-size: 0.85rem; opacity: 0.85; }}
        .success-badge {{
            display: inline-block; margin-top: 16px;
            background: rgba(255,255,255,0.2); padding: 8px 20px;
            border-radius: 999px; font-weight: 600; font-size: 0.9rem;
            letter-spacing: 0.5px;
        }}
        .receipt-body {{ padding: 30px; }}
        .receipt-meta {{
            display: flex; justify-content: space-between; flex-wrap: wrap;
            gap: 12px; margin-bottom: 28px;
            padding-bottom: 20px; border-bottom: 2px dashed #e2e8f0;
        }}
        .meta-item {{ }}
        .meta-label {{ font-size: 0.75rem; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }}
        .meta-value {{ font-size: 0.95rem; font-weight: 600; color: #1e293b; margin-top: 2px; }}
        .section-title {{
            font-size: 0.85rem; font-weight: 600; color: #1e3a8a;
            margin-bottom: 12px; display: flex; align-items: center; gap: 6px;
            text-transform: uppercase; letter-spacing: 0.05em;
        }}
        .info-grid {{
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 16px; margin-bottom: 28px;
        }}
        .info-box {{ }}
        .info-label {{ font-size: 0.75rem; color: #64748b; font-weight: 500; }}
        .info-val {{ font-size: 0.95rem; font-weight: 600; color: #1e293b; }}
        .amount-box {{
            background: #f0fdf4; border: 1px solid #bbf7d0;
            border-radius: 12px; padding: 20px; text-align: center;
            margin-bottom: 28px;
        }}
        .amount-box .amount-label {{ font-size: 0.8rem; color: #15803d; font-weight: 500; }}
        .amount-box .amount-value {{ font-size: 2rem; font-weight: 700; color: #15803d; }}
        .amount-box .amount-status {{ font-size: 0.85rem; color: #15803d; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
        th {{
            background: #f8fafc; padding: 10px 14px; text-align: left;
            font-size: 0.75rem; font-weight: 600; color: #64748b;
            text-transform: uppercase; letter-spacing: 0.05em;
            border-bottom: 1px solid #e2e8f0;
        }}
        .receipt-footer {{
            background: #f8fafc; padding: 20px 30px;
            text-align: center; font-size: 0.8rem; color: #64748b;
            border-top: 1px solid #e2e8f0;
        }}
        .print-btn {{
            display: block; width: 100%; max-width: 280px;
            margin: 24px auto 0; padding: 12px 24px;
            background: #1e3a8a; color: white; border: none;
            border-radius: 10px; font-family: inherit;
            font-size: 0.95rem; font-weight: 600; cursor: pointer;
            transition: all 0.2s;
        }}
        .print-btn:hover {{ background: #172554; transform: translateY(-1px); }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .receipt-container {{ box-shadow: none; border-radius: 0; }}
            .print-btn {{ display: none !important; }}
            .no-print {{ display: none !important; }}
        }}
        @media (max-width: 500px) {{
            .info-grid {{ grid-template-columns: 1fr; }}
            .receipt-meta {{ flex-direction: column; }}
            .receipt-header h1 {{ font-size: 1.3rem; }}
            .amount-box .amount-value {{ font-size: 1.6rem; }}
        }}
    </style>
</head>
<body>
    <div class="receipt-container">
        <div class="receipt-header">
            <h1>GPH Fine Payment Receipt</h1>
            <p>Government Polytechnic, Hamirpur (H.P.)</p>
            <div class="success-badge">✓ PAYMENT SUCCESSFUL</div>
        </div>

        <div class="receipt-body">
            <div class="receipt-meta">
                <div class="meta-item">
                    <div class="meta-label">Receipt No.</div>
                    <div class="meta-value">{receipt_no}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Payment Date</div>
                    <div class="meta-value">{payment_date_str}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Transaction ID</div>
                    <div class="meta-value">{fine.transaction_id or 'N/A'}</div>
                </div>
            </div>

            <div class="section-title">&#128100; Student Details</div>
            <div class="info-grid">
                <div class="info-box">
                    <div class="info-label">Student Name</div>
                    <div class="info-val">{student.name}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Roll Number</div>
                    <div class="info-val">{student.roll_no}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Branch</div>
                    <div class="info-val">{student.branch}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Semester</div>
                    <div class="info-val">{student.semester}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Session</div>
                    <div class="info-val">{student.academic_year}</div>
                </div>
            </div>

            <div class="section-title">&#128176; Payment Summary</div>
            <div class="amount-box">
                <div class="amount-label">Amount Paid</div>
                <div class="amount-value">₹ {fine.amount:.0f}</div>
                <div class="amount-status">✓ Paid Successfully</div>
            </div>

            <div class="section-title">&#9989; Clearance Approvals</div>
            <table>
                <thead>
                    <tr>
                        <th>Role</th>
                        <th>Faculty</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {clearance_rows}
                </tbody>
            </table>

            <button class="print-btn no-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
        </div>

        <div class="receipt-footer">
            <p>This is a computer-generated receipt. No signature required.</p>
            <p style="margin-top: 4px;">GPH Automated Fine Payment System &copy; {datetime.now().year}</p>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)


def verify_payment(roll_no: str, data: PaymentVerificationRequest, db: Session):
    """Verify Razorpay payment signature and update database."""
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Razorpay not configured")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    # Verify signature
    params_dict = {
        'razorpay_order_id': data.razorpay_order_id,
        'razorpay_payment_id': data.razorpay_payment_id,
        'razorpay_signature': data.razorpay_signature
    }

    try:
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")

    # Payment verified successfully
    fine = (
        db.query(Fine)
        .filter(Fine.roll_no == roll_no, Fine.semester == student.semester)
        .first()
    )
    if not fine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No fine record found")

    # Update fine status
    fine.status = "Paid"
    fine.payment_date = datetime.now(timezone.utc)
    fine.transaction_id = data.razorpay_payment_id

    # Update student status to Cleared
    student.status = "Cleared"

    db.commit()

    return {"message": "Payment verified successfully", "transaction_id": data.razorpay_payment_id}
