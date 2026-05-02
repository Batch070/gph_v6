from typing import Optional
"""Business logic for Class Incharge–specific endpoints."""

import io
import csv
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.student import Student
from app.models.faculty import Faculty
from app.models.request import Request
from app.models.fine import Fine
from app.utils.semester import is_semester_active


# ── Overview ──────────────────────────────────────────────────
def get_overview(faculty_id: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    # Students assigned to this specific incharge
    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.class_incharge_id == faculty_id).all()
    roll_nos = [s.roll_no for s in students]

    total_students = len(students)

    # Fine aggregates
    fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos)).all() if roll_nos else []
    total_fine = sum(f.amount for f in fines)
    collected = sum(f.amount for f in fines if f.status == "Paid")
    remaining = sum(f.amount for f in fines if f.status == "Unpaid")

    # Request counts (only for THIS faculty's requests)
    pending_count = 0
    approved_count = 0
    rejected_count = 0
    if roll_nos:
        pending_count = (
            db.query(Request)
            .filter(Request.roll_no.in_(roll_nos), Request.faculty_id == faculty_id, Request.status == "Pending")
            .count()
        )
        approved_count = (
            db.query(Request)
            .filter(Request.roll_no.in_(roll_nos), Request.faculty_id == faculty_id, Request.status == "Approved")
            .count()
        )
        rejected_count = (
            db.query(Request)
            .filter(Request.roll_no.in_(roll_nos), Request.faculty_id == faculty_id, Request.status == "Rejected")
            .count()
        )

    # Student DB insights
    avg_theory = 0
    avg_practical = 0
    hosteller_count = 0
    ncc_count = 0
    if total_students > 0:
        avg_theory = round(
            sum(s.theory_attendance or 0 for s in students) / total_students, 1
        )
        avg_practical = round(
            sum(s.practical_attendance or 0 for s in students) / total_students, 1
        )
        hosteller_count = sum(1 for s in students if s.hosteller)
        ncc_count = sum(1 for s in students if s.ncc)

    # Paid / unpaid student counts
    paid_roll_nos = set(f.roll_no for f in fines if f.status == "Paid")
    unpaid_roll_nos = set(f.roll_no for f in fines if f.status == "Unpaid") - paid_roll_nos
    paid_count = len(paid_roll_nos)
    unpaid_count = len(unpaid_roll_nos)

    # Honorific for the faculty
    honorific = "Mrs. " if faculty.gender == "Female" else "Mr. "

    return {
        "faculty_name": f"{honorific}{faculty.name}",
        "faculty_role": faculty.role,
        "branch": branch,
        "total_students": total_students,
        "total_fine": total_fine,
        "collected": collected,
        "remaining": remaining,
        "pending_requests": pending_count,
        "approved_requests": approved_count,
        "rejected_requests": rejected_count,
        "avg_theory_attendance": avg_theory,
        "avg_practical_attendance": avg_practical,
        "hosteller_count": hosteller_count,
        "ncc_count": ncc_count,
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
    }


# ── Student list by semester ──────────────────────────────────
def get_students(faculty_id: int, semester: Optional[int], db: Session) -> list[dict]:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    branch = faculty.branch or "Information Technology"
    query = db.query(Student).filter(Student.class_incharge_id == faculty_id)
    if semester:
        query = query.filter(Student.semester == semester)

    students = query.all()
    result = []
    for s in students:
        # Get request assigned to THIS faculty for this student
        req = (
            db.query(Request)
            .filter(Request.roll_no == s.roll_no, Request.faculty_id == faculty_id)
            .first()
        )
        # Get fine info
        fine = (
            db.query(Fine)
            .filter(Fine.roll_no == s.roll_no, Fine.semester == s.semester)
            .first()
        )
        result.append({
            "roll_no": s.roll_no,
            "name": s.name,
            "semester": s.semester,
            "branch": s.branch,
            "fine_amount": fine.amount if fine else 0,
            "fine_status": fine.status if fine else "N/A",
            "request_id": req.id if req else None,
            "request_status": req.status if req else None,
            "request_note": req.note if req else None,
            "theory_attendance": s.theory_attendance or 0,
            "practical_attendance": s.practical_attendance or 0,
            "student_status": s.status or "Pending",
            "ncc": s.ncc,
            "hosteller": s.hosteller,
        })
    return result


# ── Semesters available ───────────────────────────────────────
def get_semesters(faculty_id: int, db: Session) -> list[dict]:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    branch = faculty.branch or "Information Technology"
    rows = (
        db.query(Student.semester, func.count(Student.roll_no))
        .filter(Student.class_incharge_id == faculty_id)
        .group_by(Student.semester)
        .all()
    )

    result = []
    for sem, count in rows:
        pending = (
            db.query(Request)
            .join(Student, Student.roll_no == Request.roll_no)
            .filter(
                Student.class_incharge_id == faculty_id,
                Student.semester == sem,
                Request.faculty_id == faculty_id,
                Request.status == "Pending",
            )
            .count()
        )
        result.append({
            "semester": sem, 
            "student_count": count, 
            "pending_requests": pending,
            "is_active": is_semester_active(sem)
        })
    return result


# ── Student profile detail ────────────────────────────────────
def get_student_profile(faculty_id: int, roll_no: str, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")

    # All requests for this student
    requests = db.query(Request).filter(Request.roll_no == roll_no).all()
    approvals = []
    for req in requests:
        fac = db.query(Faculty).filter(Faculty.id == req.faculty_id).first()
        honorific = ""
        if fac:
            honorific = "Mrs. " if fac.gender == "Female" else "Mr. "
        approvals.append({
            "request_id": req.id,
            "faculty_name": f"{honorific}{fac.name}" if fac else "Unknown",
            "faculty_role": fac.role if fac else "Unknown",
            "status": req.status,
            "note": req.note,
            "action_date": str(req.action_date) if req.action_date else None,
        })

    # Fine info
    fines = db.query(Fine).filter(Fine.roll_no == roll_no).all()
    total_fine = sum(f.amount for f in fines)
    paid = sum(f.amount for f in fines if f.status == "Paid")
    remaining = total_fine - paid

    return {
        "roll_no": student.roll_no,
        "name": student.name,
        "branch": student.branch,
        "semester": student.semester,
        "academic_year": student.academic_year,
        "ncc": student.ncc,
        "hosteller": student.hosteller,
        "theory_attendance": student.theory_attendance or 0,
        "practical_attendance": student.practical_attendance or 0,
        "total_fine": total_fine,
        "paid": paid,
        "remaining": remaining,
        "approvals": approvals,
    }


# ── Reports ───────────────────────────────────────────────────
def get_report(faculty_id: int, report_type: str, db: Session) -> StreamingResponse:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.class_incharge_id == faculty_id).all()
    roll_nos = [s.roll_no for s in students]
    student_map = {s.roll_no: s for s in students}

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "paid":
        writer.writerow(["Roll No", "Name", "Semester", "Amount", "Payment Date", "Transaction ID"])
        fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos), Fine.status == "Paid").all()
        for f in fines:
            s = student_map.get(f.roll_no)
            writer.writerow([
                f.roll_no, s.name if s else "", f.semester, f.amount,
                str(f.payment_date) if f.payment_date else "", f.transaction_id or ""
            ])
        filename = "paid_students.csv"

    elif report_type == "unpaid":
        writer.writerow(["Roll No", "Name", "Semester", "Amount"])
        fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos), Fine.status == "Unpaid").all()
        for f in fines:
            s = student_map.get(f.roll_no)
            writer.writerow([f.roll_no, s.name if s else "", f.semester, f.amount])
        filename = "unpaid_students.csv"

    else:  # monthly
        writer.writerow(["Roll No", "Name", "Semester", "Amount", "Status", "Payment Date"])
        fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos)).all()
        for f in fines:
            s = student_map.get(f.roll_no)
            writer.writerow([
                f.roll_no, s.name if s else "", f.semester, f.amount,
                f.status, str(f.payment_date) if f.payment_date else ""
            ])
        filename = "monthly_summary.csv"

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Reset Data ────────────────────────────────────────────────
def reset_data(faculty_id: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.class_incharge_id == faculty_id).all()
    roll_nos = [s.roll_no for s in students]

    if not roll_nos:
        return {"message": "No data to reset", "fines_deleted": 0, "requests_deleted": 0}

    fines_deleted = db.query(Fine).filter(Fine.roll_no.in_(roll_nos)).delete(synchronize_session=False)
    requests_deleted = db.query(Request).filter(Request.roll_no.in_(roll_nos)).delete(synchronize_session=False)

    # Reset student statuses and attendance data
    for s in students:
        s.status = "Pending"
        s.theory_attendance = 0.0
        s.practical_attendance = 0.0

    db.commit()

    return {
        "message": "All fine, request, and attendance data has been reset",
        "fines_deleted": fines_deleted,
        "requests_deleted": requests_deleted,
    }
