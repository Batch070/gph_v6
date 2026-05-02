from typing import Optional
"""Business logic for faculty-facing endpoints."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.student import Student
from app.models.faculty import Faculty
from app.models.request import Request
from app.schemas.faculty import (
    FacultyDashboard,
    StudentListItem,
    UpdateRequestResponse,
)


def get_dashboard(faculty_id: int, db: Session) -> FacultyDashboard:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    students: list[StudentListItem] = []

    if faculty.role == "ClassIncharge":
        # ClassIncharge sees students of their branch with requests assigned to them
        rows = (
            db.query(Student, Request)
            .outerjoin(Request, (Request.roll_no == Student.roll_no) & (Request.faculty_id == faculty.id))
            .filter(Student.branch == faculty.branch)
            .all()
        )
        for s, r in rows:
            if r is not None:  # only show students who have requests for this faculty
                students.append(_to_item(s, r))

    elif faculty.role == "HOD":
        # HOD can see ALL students in their branch
        rows = (
            db.query(Student, Request)
            .outerjoin(Request, (Request.roll_no == Student.roll_no) & (Request.faculty_id == faculty.id))
            .filter(Student.branch == faculty.branch)
            .all()
        )
        for s, r in rows:
            students.append(_to_item(s, r))

    else:
        # PTI, Librarian, CanteenOwner, ANO, Warden
        query = db.query(Student, Request).outerjoin(
            Request, (Request.roll_no == Student.roll_no) & (Request.faculty_id == faculty.id)
        )
        
        if faculty.role == "ANO":
            query = query.filter(Student.ncc == True)
        elif faculty.role == "HostelSuperintendent_Boys":
            query = query.filter(Student.hosteller == True, Student.gender.in_(["Male", "M"]))
        elif faculty.role == "HostelSuperintendent_Girls":
            query = query.filter(Student.hosteller == True, Student.gender.in_(["Female", "F"]))
            
        rows = query.all()
        for s, r in rows:
            students.append(_to_item(s, r))

    return FacultyDashboard(
        faculty_name=faculty.name,
        faculty_role=faculty.role,
        students=students,
    )


def get_hod_students(
    faculty_id: int, db: Session, semester: Optional[int] = None
) -> list[StudentListItem]:
    """HOD-specific view — all IT students with optional semester filter."""
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    query = db.query(Student, Request).outerjoin(
        Request,
        (Request.roll_no == Student.roll_no) & (Request.faculty_id == faculty.id),
    ).filter(Student.branch == faculty.branch)

    if semester is not None:
        query = query.filter(Student.semester == semester)

    rows = query.all()
    return [_to_item(s, r) for s, r in rows]


def update_request(
    request_id: int,
    faculty_id: int,
    new_status: str,
    note: Optional[str],
    db: Session,
) -> UpdateRequestResponse:
    if new_status not in ("Approved", "Rejected", "Pending"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'Approved', 'Rejected', or 'Pending'",
        )

    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.faculty_id != faculty_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You are not authorised to update this request",
        )

    # Unlock flow: changing back to Pending requires the request to NOT already be Pending
    if new_status == "Pending":
        if req.status == "Pending":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Request is already Pending.",
            )
    else:
        # Normal approve/reject flow: request must be Pending
        if req.status != "Pending":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Request already {req.status}. Cannot update again.",
            )

    req.status = new_status
    req.note = note if new_status != "Pending" else None
    req.action_date = datetime.now(timezone.utc) if new_status != "Pending" else None
    db.commit()
    db.refresh(req)

    # Check if all requests for this student are now approved → update student status
    student = db.query(Student).filter(Student.roll_no == req.roll_no).first()
    if new_status == "Approved":
        all_reqs = db.query(Request).filter(Request.roll_no == req.roll_no).all()
        if all(r.status == "Approved" for r in all_reqs):
            if student:
                from app.models.fine import Fine
                fine = db.query(Fine).filter(Fine.roll_no == student.roll_no, Fine.semester == student.semester).first()
                if fine and fine.amount <= 0:
                    student.status = "Cleared"
                else:
                    student.status = "Approved"
                db.commit()
    elif new_status in ("Rejected", "Pending"):
        # Revert student status back to Pending if it was Approved
        if student and student.status == "Approved":
            student.status = "Pending"
            db.commit()
            
    # Send email notification for request status change
    if student and student.email and new_status in ("Approved", "Rejected"):
        from app.utils.email import send_student_notification, get_html_template
        faculty_name = "A faculty member" # Ideally we'd get the actual name from faculty_id
        faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
        if faculty:
            faculty_name = f"{faculty.name} ({faculty.role})"
            
        color = "#27ae60" if new_status == "Approved" else "#e74c3c"
        html_content = get_html_template(
            "Clearance Request Updated",
            f"<p>Dear {student.name},</p><p>Your clearance request has been <strong><span style='color: {color}'>{new_status}</span></strong> by {faculty_name}.</p>" + 
            (f"<p><strong>Note:</strong> {note}</p>" if note else "") +
            "<p>Please log in to the portal to view your complete clearance status.</p>"
        )
        send_student_notification(student.email, f"GPH - Clearance Request {new_status}", html_content)

    action_label = "unlocked" if new_status == "Pending" else new_status.lower()
    return UpdateRequestResponse(
        message=f"Request {action_label} successfully",
        request_id=req.id,
        new_status=req.status,
    )

def bulk_update_requests(
    request_ids: list[int],
    faculty_id: int,
    status: str,
    db: Session,
) -> int:
    """Updates multiple requests at once."""
    if status not in ("Approved", "Rejected"):
        # Bulk updates usually only target terminal states
        raise HTTPException(400, "Status must be 'Approved' or 'Rejected'")

    if not request_ids:
        return 0

    # Fetch all requests that belong to this faculty and are in the specified list
    requests = db.query(Request).filter(
        Request.id.in_(request_ids),
        Request.faculty_id == faculty_id,
        Request.status == "Pending",
    ).all()

    if not requests:
        return 0

    roll_nos = set()
    for req in requests:
        req.status = status
        req.action_date = datetime.now(timezone.utc)
        roll_nos.add(req.roll_no)
    
    db.commit()

    # Re-evaluate student statuses
    if status == "Approved" or status == "Rejected":
        students = db.query(Student).filter(Student.roll_no.in_(roll_nos)).all()
        student_map = {s.roll_no: s for s in students}
        
        all_reqs = db.query(Request).filter(Request.roll_no.in_(roll_nos)).all()
        # Group logic
        from collections import defaultdict
        req_map = defaultdict(list)
        for r in all_reqs:
            req_map[r.roll_no].append(r)

        # Re-evaluate student statuses and send emails
        from app.utils.email import send_student_notification, get_html_template
        faculty_name = "Your faculty"
        faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
        if faculty:
            faculty_name = f"{faculty.name} ({faculty.role})"
            
        for roll_no, reqs in req_map.items():
            stu = student_map.get(roll_no)
            if not stu:
                continue

            if status == "Approved":
                if all(r.status == "Approved" for r in reqs):
                    from app.models.fine import Fine
                    fine = db.query(Fine).filter(Fine.roll_no == stu.roll_no, Fine.semester == stu.semester).first()
                    if fine and fine.amount <= 0:
                        stu.status = "Cleared"
                    else:
                        stu.status = "Approved"
            else:
                if stu.status == "Approved":
                    stu.status = "Pending"
            
            # Send email
            if stu.email:
                color = "#27ae60" if status == "Approved" else "#e74c3c"
                html_content = get_html_template(
                    "Clearance Request Updated",
                    f"<p>Dear {stu.name},</p><p>Your clearance request has been <strong><span style='color: {color}'>{status}</span></strong> by {faculty_name}.</p><p>Please log in to the portal to view your complete clearance status.</p>"
                )
                send_student_notification(stu.email, f"GPH - Clearance Request {status}", html_content)

        db.commit()

    return len(requests)


# ── helpers ───────────────────────────────────────────────────
def _to_item(s: Student, r: Optional[Request]) -> StudentListItem:
    return StudentListItem(
        roll_no=s.roll_no,
        name=s.name,
        branch=s.branch,
        semester=s.semester,
        academic_year=s.academic_year,
        dob=s.dob,
        ncc=s.ncc,
        hosteller=s.hosteller,
        practical_attendance=s.practical_attendance or 0.0,
        theory_attendance=s.theory_attendance or 0.0,
        student_status=s.status or "Pending",
        request_id=r.id if r else None,
        request_status=r.status if r else None,
        request_note=r.note if r else None,
    )
