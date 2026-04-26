from typing import Optional
"""Business logic for HOD-specific endpoints."""

import io


def _detect_header_row(file_bytes: bytes) -> int:
    """Scan first 10 rows to find the row containing a 'roll' column."""
    preview = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl", header=None, nrows=10)
    for idx, row in preview.iterrows():
        values = [str(v).lower().strip() for v in row.values if pd.notna(v)]
        if any("roll" in v for v in values):
            return int(idx)
    return 0
import csv
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.models.student import Student
from app.models.faculty import Faculty
from app.models.request import Request
from app.models.fine import Fine


# ── Overview ──────────────────────────────────────────────────
def get_overview(faculty_id: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.branch == branch).all()
    roll_nos = [s.roll_no for s in students]

    total_students = len(students)
    total_faculty = db.query(Faculty).filter(Faculty.branch == branch).count()

    # Fine aggregates
    fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos)).all() if roll_nos else []
    total_fine = sum(f.amount for f in fines)
    collected = sum(f.amount for f in fines if f.status == "Paid")
    remaining = sum(f.amount for f in fines if f.status == "Unpaid")

    # Request counts (HOD-level requests only)
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

    # Honorific
    honorific = "Mrs. " if faculty.gender == "Female" else "Mr. "

    return {
        "faculty_name": f"{honorific}{faculty.name}",
        "faculty_role": faculty.role,
        "branch": branch,
        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_fine": total_fine,
        "collected": collected,
        "remaining": remaining,
        "pending_requests": pending_count,
        "approved_requests": approved_count,
        "rejected_requests": rejected_count,
    }


# ── Semesters available ───────────────────────────────────────
def get_semesters(faculty_id: int, db: Session) -> list[dict]:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    rows = (
        db.query(Student.semester, func.count(Student.roll_no))
        .filter(Student.branch == branch)
        .group_by(Student.semester)
        .all()
    )

    result = []
    for sem, count in rows:
        pending = (
            db.query(Request)
            .join(Student, Student.roll_no == Request.roll_no)
            .filter(
                Student.branch == branch,
                Student.semester == sem,
                Request.faculty_id == faculty_id,
                Request.status == "Pending",
            )
            .count()
        )
        result.append({"semester": sem, "student_count": count, "pending_requests": pending})
    return result


# ── Student list by semester ──────────────────────────────────
def get_students(faculty_id: int, semester: Optional[int], db: Session) -> list[dict]:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    query = db.query(Student).filter(Student.branch == branch)
    if semester:
        query = query.filter(Student.semester == semester)

    students = query.all()
    result = []
    for s in students:
        # Get request assigned to HOD for this student
        req = (
            db.query(Request)
            .filter(Request.roll_no == s.roll_no, Request.faculty_id == faculty_id)
            .first()
        )
        # Check if class incharge has cleared
        ic_req = (
            db.query(Request)
            .join(Faculty, Faculty.id == Request.faculty_id)
            .filter(Request.roll_no == s.roll_no, Faculty.role == "ClassIncharge")
            .first()
        )
        ic_status = ic_req.status if ic_req else "No Request"

        # Fine info
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
            "incharge_status": ic_status,
            "theory_attendance": s.theory_attendance or 0,
            "practical_attendance": s.practical_attendance or 0,
            "student_status": s.status or "Pending",
        })
    return result


# ── Student profile detail ────────────────────────────────────
def get_student_profile(faculty_id: int, roll_no: str, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

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


# ── Faculty list (IT Department only) ─────────────────────────
def get_faculty_list(faculty_id: int, db: Session) -> list[dict]:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    # Only fetch IT department faculty (HOD + ClassIncharge), not college-wide roles
    it_dept_roles = ["HOD", "ClassIncharge"]
    faculty_list = (
        db.query(Faculty)
        .filter(Faculty.branch == branch, Faculty.role.in_(it_dept_roles))
        .all()
    )

    result = []
    for f in faculty_list:
        # Find assigned classes (semesters where this faculty is class incharge)
        assigned = []
        if f.role == "ClassIncharge":
            semesters = (
                db.query(Student.semester)
                .filter(Student.class_incharge_id == f.id)
                .distinct()
                .all()
            )
            assigned = [f"IT {s[0]}th Sem" for s in semesters]

        honorific = "Mrs. " if f.gender == "Female" else "Mr. "
        result.append({
            "id": f.id,
            "name": f"{honorific}{f.name}",
            "raw_name": f.name,
            "gender": f.gender,
            "role": f.role,
            "assigned_classes": ", ".join(assigned) if assigned else f.role,
            "username": f.username,
            "status": "Active",
        })
    return result


# ── Add Faculty to Department ─────────────────────────────────
def add_faculty(
    faculty_id: int,
    name: str,
    username: str,
    password: str,
    role: str,
    gender: Optional[str],
    db: Session,
) -> dict:
    from app.utils.security import hash_password

    hod = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not hod or hod.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    # HOD can only add ClassIncharge faculty
    role = "ClassIncharge"

    # Check username uniqueness
    existing = db.query(Faculty).filter(Faculty.username == username).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Username '{username}' already exists")

    branch = hod.branch or "Information Technology"

    new_faculty = Faculty(
        name=name,
        username=username,
        password=hash_password(password),
        role=role,
        branch=branch,
        gender=gender,
    )
    db.add(new_faculty)
    db.commit()
    db.refresh(new_faculty)

    return {
        "message": f"Faculty '{name}' added successfully",
        "faculty_id": new_faculty.id,
    }


# ── Update Faculty Role ───────────────────────────────────────
def update_faculty_role(
    faculty_id: int,
    target_faculty_id: int,
    new_role: str,
    db: Session,
) -> dict:
    hod = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not hod or hod.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = hod.branch or "Information Technology"

    target = db.query(Faculty).filter(Faculty.id == target_faculty_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty member not found")

    # Only manage faculty in same branch
    if target.branch != branch:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot modify faculty outside your department")

    # Prevent changing to HOD or Admin
    if new_role in ("HOD", "Admin"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot assign HOD or Admin role")

    # Prevent HOD from changing their own role
    if target.id == hod.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    old_role = target.role
    target.role = new_role
    db.commit()

    return {
        "message": f"Role updated from '{old_role}' to '{new_role}' for {target.name}",
        "faculty_id": target.id,
        "new_role": new_role,
    }


# ── Remove Faculty from Department ────────────────────────────
def remove_faculty(
    faculty_id: int,
    target_faculty_id: int,
    db: Session,
) -> dict:
    hod = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not hod or hod.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = hod.branch or "Information Technology"

    target = db.query(Faculty).filter(Faculty.id == target_faculty_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty member not found")

    if target.branch != branch:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot remove faculty outside your department")

    if target.id == hod.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    if target.role == "HOD":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot remove another HOD")

    # Unassign students that had this faculty as class incharge
    db.query(Student).filter(Student.class_incharge_id == target.id).update(
        {Student.class_incharge_id: None}, synchronize_session=False
    )

    # Delete their pending requests
    db.query(Request).filter(Request.faculty_id == target.id).delete(synchronize_session=False)

    faculty_name = target.name
    db.delete(target)
    db.commit()

    return {"message": f"Faculty '{faculty_name}' removed from department"}


# ── Assign Class Incharge to Semester ─────────────────────────
def assign_class_incharge(
    faculty_id: int,
    target_faculty_id: int,
    semester: int,
    db: Session,
) -> dict:
    hod = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not hod or hod.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = hod.branch or "Information Technology"

    target = db.query(Faculty).filter(Faculty.id == target_faculty_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty member not found")

    if target.branch != branch:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot assign faculty outside your department")

    # Check if there are actually any students in this semester to assign
    student_count = db.query(Student).filter(
        Student.branch == branch,
        Student.semester == semester
    ).count()

    if student_count == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 
            detail=f"Cannot assign incharge: No students found for Semester {semester}. Please upload student data first."
        )

    # Update their role to ClassIncharge
    target.role = "ClassIncharge"

    # Remove previous class incharge for this semester (unassign students)
    db.query(Student).filter(
        Student.branch == branch,
        Student.semester == semester,
        Student.class_incharge_id != target.id,
    ).update({Student.class_incharge_id: None}, synchronize_session=False)

    # Assign this faculty to all students in the semester
    db.query(Student).filter(
        Student.branch == branch,
        Student.semester == semester,
    ).update({Student.class_incharge_id: target.id}, synchronize_session=False)

    db.commit()

    honorific = "Mrs. " if target.gender == "Female" else "Mr. "
    return {
        "message": f"{honorific}{target.name} assigned as Class Incharge for Semester {semester}",
        "faculty_id": target.id,
        "semester": semester,
    }

# ── Reports ───────────────────────────────────────────────────
def get_report(faculty_id: int, report_type: str, db: Session) -> StreamingResponse:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.branch == branch).all()
    roll_nos = [s.roll_no for s in students]
    student_map = {s.roll_no: s for s in students}

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "collection":
        writer.writerow(["Roll No", "Name", "Semester", "Fine Amount", "Status", "Payment Date", "Transaction ID"])
        fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos)).all() if roll_nos else []
        for f in fines:
            s = student_map.get(f.roll_no)
            writer.writerow([
                f.roll_no, s.name if s else "", f.semester, f.amount,
                f.status, str(f.payment_date) if f.payment_date else "", f.transaction_id or ""
            ])
        filename = "department_fine_collection.csv"

    elif report_type == "defaulter":
        writer.writerow(["Roll No", "Name", "Semester", "Unpaid Amount"])
        fines = db.query(Fine).filter(Fine.roll_no.in_(roll_nos), Fine.status == "Unpaid").all() if roll_nos else []
        for f in fines:
            s = student_map.get(f.roll_no)
            writer.writerow([f.roll_no, s.name if s else "", f.semester, f.amount])
        filename = "defaulter_list.csv"

    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid report type. Use 'collection' or 'defaulter'.")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Upload Branch Data ────────────────────────────────────────
def upload_branch_data(file: UploadFile, faculty_id: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    filename = file.filename or ""
    if not filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Only .xlsx, .xls, .csv files accepted")

    try:
        contents = file.file.read()
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            header_row = _detect_header_row(contents)
            df = pd.read_excel(io.BytesIO(contents), engine="openpyxl", header=header_row)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Failed to read file: {exc}")

    # Normalize columns
    col_map = {}
    for col in df.columns:
        lower = str(col).lower().strip().replace(" ", "_")
        if "roll" in lower:
            col_map[col] = "roll_no"
        elif lower in ("name", "student_name"):
            col_map[col] = "name"
        elif lower in ("semester", "sem"):
            col_map[col] = "semester"
        elif lower in ("academic_year", "year"):
            col_map[col] = "academic_year"
        elif "dob" in lower or "birth" in lower:
            col_map[col] = "dob"
        elif lower in ("gender", "sex"):
            col_map[col] = "gender"
        elif "ncc" in lower:
            col_map[col] = "ncc"
        elif "hostel" in lower:
            col_map[col] = "hosteller"
    df.rename(columns=col_map, inplace=True)

    required = {"roll_no", "name", "semester", "dob"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"File must contain columns: {', '.join(required)}. Found: {', '.join(df.columns)}",
        )

    branch = faculty.branch or "Information Technology"
    inserted = 0
    updated = 0
    errors = []

    for idx, row in df.iterrows():
        roll_no = str(row["roll_no"]).strip()
        name = str(row["name"]).strip()
        try:
            semester = int(float(row["semester"]))
            dob = pd.to_datetime(row["dob"]).date()
        except Exception as e:
            errors.append(f"Row {idx + 2}: invalid data — {e}")
            continue

        academic_year = str(row.get("academic_year", "2025-26")).strip()
        gender = str(row.get("gender", "")).strip() if "gender" in df.columns else None
        ncc = bool(row.get("ncc", False)) if "ncc" in df.columns else False
        hosteller = bool(row.get("hosteller", False)) if "hosteller" in df.columns else False

        existing = db.query(Student).filter(Student.roll_no == roll_no).first()
        if existing:
            existing.name = name
            existing.semester = semester
            existing.dob = dob
            existing.branch = branch
            existing.academic_year = academic_year
            existing.hod_id = faculty_id
            if gender:
                existing.gender = gender
            updated += 1
        else:
            new_student = Student(
                roll_no=roll_no,
                name=name,
                branch=branch,
                semester=semester,
                academic_year=academic_year,
                dob=dob,
                gender=gender,
                ncc=ncc,
                hosteller=hosteller,
                hod_id=faculty_id,
            )
            db.add(new_student)
            inserted += 1

    db.commit()
    return {
        "message": "Branch data upload processed",
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
    }


# ── Upload Semester Data ──────────────────────────────────────
def upload_semester_data(file: UploadFile, semester: int, faculty_id: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    filename = file.filename or ""
    if not filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Only .xlsx, .xls, .csv files accepted")

    try:
        contents = file.file.read()
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            header_row = _detect_header_row(contents)
            df = pd.read_excel(io.BytesIO(contents), engine="openpyxl", header=header_row)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Failed to read file: {exc}")

    # Normalize columns
    col_map = {}
    for col in df.columns:
        lower = str(col).lower().strip().replace(" ", "_")
        if "roll" in lower:
            col_map[col] = "roll_no"
        elif lower in ("name", "student_name"):
            col_map[col] = "name"
        elif "dob" in lower or "birth" in lower:
            col_map[col] = "dob"
        elif lower in ("gender", "sex"):
            col_map[col] = "gender"
        elif "ncc" in lower:
            col_map[col] = "ncc"
        elif "hostel" in lower:
            col_map[col] = "hosteller"
        elif "theory" in lower:
            col_map[col] = "theory_attendance"
        elif "practical" in lower or "pract" in lower:
            col_map[col] = "practical_attendance"
    df.rename(columns=col_map, inplace=True)

    required = {"roll_no", "name", "dob"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"File must contain columns: {', '.join(required)}. Found: {', '.join(df.columns)}",
        )

    branch = faculty.branch or "Information Technology"
    inserted = 0
    updated = 0
    errors = []

    for idx, row in df.iterrows():
        roll_no = str(row["roll_no"]).strip()
        name = str(row["name"]).strip()
        try:
            dob = pd.to_datetime(row["dob"]).date()
        except Exception as e:
            errors.append(f"Row {idx + 2}: invalid data — {e}")
            continue

        gender = str(row.get("gender", "")).strip() if "gender" in df.columns else None
        ncc = bool(row.get("ncc", False)) if "ncc" in df.columns else False
        hosteller = bool(row.get("hosteller", False)) if "hosteller" in df.columns else False

        existing = db.query(Student).filter(Student.roll_no == roll_no).first()
        if existing:
            existing.name = name
            existing.semester = semester
            existing.dob = dob
            existing.branch = branch
            existing.hod_id = faculty_id
            if gender:
                existing.gender = gender
            if "theory_attendance" in df.columns:
                try:
                    existing.theory_attendance = float(row["theory_attendance"])
                except (ValueError, TypeError):
                    pass
            if "practical_attendance" in df.columns:
                try:
                    existing.practical_attendance = float(row["practical_attendance"])
                except (ValueError, TypeError):
                    pass
            updated += 1
        else:
            new_student = Student(
                roll_no=roll_no,
                name=name,
                branch=branch,
                semester=semester,
                academic_year="2025-26",
                dob=dob,
                gender=gender,
                ncc=ncc,
                hosteller=hosteller,
                hod_id=faculty_id,
            )
            db.add(new_student)
            inserted += 1

    db.commit()
    return {
        "message": f"Semester {semester} data upload processed",
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
    }


# ── Reset All Data ────────────────────────────────────────────
def reset_data(faculty_id: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.branch == branch).all()
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
        "message": "All fine, request, and attendance data has been reset for the department",
        "fines_deleted": fines_deleted,
        "requests_deleted": requests_deleted,
    }

# ── Delete Semester Data ──────────────────────────────────────
def delete_semester_data(faculty_id: int, semester: int, db: Session) -> dict:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty or faculty.role != "HOD":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="HOD access required")

    branch = faculty.branch or "Information Technology"
    students = db.query(Student).filter(Student.branch == branch, Student.semester == semester).all()
    roll_nos = [s.roll_no for s in students]

    if not roll_nos:
        return {"message": "No students found for this semester", "deleted_students": 0}

    fines_deleted = db.query(Fine).filter(Fine.roll_no.in_(roll_nos)).delete(synchronize_session=False)
    requests_deleted = db.query(Request).filter(Request.roll_no.in_(roll_nos)).delete(synchronize_session=False)
    students_deleted = db.query(Student).filter(Student.roll_no.in_(roll_nos)).delete(synchronize_session=False)

    db.commit()

    return {
        "message": f"Successfully deleted {students_deleted} students from Semester {semester}",
        "deleted_students": students_deleted,
        "deleted_fines": fines_deleted,
        "deleted_requests": requests_deleted,
    }

def get_db_insights(faculty_id: int, db: Session):
    from sqlalchemy import func, Integer
    from app.models.faculty import Faculty
    from app.models.student import Student
    
    hod = db.query(Faculty).filter(Faculty.id == faculty_id, Faculty.role == "HOD").first()
    if not hod:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not HOD")
        
    rows = db.query(
        Student.semester,
        Faculty.name,
        func.count(Student.roll_no).label("student_count")
    ).outerjoin(Faculty, Student.class_incharge_id == Faculty.id)\
    .filter(Student.branch == hod.branch)\
    .group_by(Student.semester, Faculty.name).all()
    
    results = []
    for sem, incharge_name, count in rows:
        results.append({
            "branch": hod.branch or "Information Technology",
            "semester": sem,
            "incharge_name": incharge_name or "Not Assigned",
            "total_students": count
        })
        
    overall = db.query(
        func.sum(func.cast(Student.ncc, Integer)).label("total_ncc"),
        func.sum(func.cast(Student.hosteller, Integer)).label("total_hosteller"),
        func.sum(func.cast(Student.status == "Pending", Integer)).label("total_pending"),
        func.sum(func.cast(Student.status == "Approved", Integer)).label("total_accepted")
    ).filter(Student.branch == hod.branch).first()
    
    overall_stats = {
        "total_ncc": int(overall.total_ncc or 0),
        "total_hosteller": int(overall.total_hosteller or 0),
        "total_pending": int(overall.total_pending or 0),
        "total_accepted": int(overall.total_accepted or 0)
    }

    return {"overall_stats": overall_stats, "insights": results}
