"""Business logic for admin-facing endpoints (fine upload via Excel/PDF)."""

import pandas as pd
import pdfplumber
import io
import re
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.fine import Fine
from app.models.student import Student
from app.schemas.fine import FineUploadResponse


def _parse_pdf_to_dataframe(file_bytes: bytes) -> pd.DataFrame:
    """
    Extract the first table from a PDF and return it as a DataFrame.

    Tries pdfplumber table extraction first. If no table is found,
    falls back to line-by-line text parsing.
    """
    rows = []
    headers = None

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # Try structured table extraction
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for i, row in enumerate(table):
                        # Clean cells
                        cleaned = [
                            (cell.strip() if cell else "") for cell in row
                        ]
                        if headers is None:
                            # Normalize header names
                            headers = [
                                h.lower().replace(" ", "_").replace("%", "")
                                for h in cleaned
                            ]
                        else:
                            rows.append(cleaned)
            else:
                # Fallback: parse text lines
                text = page.extract_text()
                if text:
                    for line in text.split("\n"):
                        parts = re.split(r"\s{2,}|\t", line.strip())
                        if len(parts) < 3:
                            continue
                        if headers is None:
                            headers = [
                                h.lower().replace(" ", "_").replace("%", "")
                                for h in parts
                            ]
                        else:
                            rows.append(parts)

    if not headers or not rows:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Could not extract any table data from the PDF. "
                   "Ensure rows have columns: roll_no, amount, semester.",
        )

    df = pd.DataFrame(rows, columns=headers[: max(len(r) for r in rows)])
    return df


def _detect_header_row(file_bytes: bytes) -> int:
    """
    Scan the first 10 rows of an Excel file to find the actual header row.
    Returns the 0-based index of the row containing a 'roll' column.
    Falls back to 0 if no such row is found.
    """
    preview = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl", header=None, nrows=10)
    for idx, row in preview.iterrows():
        values = [str(v).lower().strip() for v in row.values if pd.notna(v)]
        if any("roll" in v for v in values):
            return int(idx)
    return 0


def upload_fines(file: UploadFile, db: Session) -> FineUploadResponse:
    """
    Parse an uploaded .xlsx or .pdf file and upsert fine records.

    Required columns: roll_no, amount, semester
    Optional columns: theory_attendance, practical_attendance
    """
    filename = file.filename or ""

    if filename.endswith(".xlsx"):
        try:
            contents = file.file.read()
            header_row = _detect_header_row(contents)
            df = pd.read_excel(io.BytesIO(contents), engine="openpyxl", header=header_row)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel file: {exc}",
            )
    elif filename.endswith(".pdf"):
        try:
            file_bytes = file.file.read()
            df = _parse_pdf_to_dataframe(file_bytes)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read PDF file: {exc}",
            )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx and .pdf files are accepted",
        )

    # Normalize column names (handle variations)
    col_map = {}
    for col in df.columns:
        lower = str(col).lower().strip().replace(" ", "_")
        if "roll" in lower:
            col_map[col] = "roll_no"
        elif "amount" in lower or lower in ("fine",):
            col_map[col] = "amount"
        elif "semester" in lower or lower == "sem":
            col_map[col] = "semester"
        elif "theory" in lower:
            col_map[col] = "theory_attendance"
        elif "practical" in lower or "pract" in lower:
            col_map[col] = "practical_attendance"
    df.rename(columns=col_map, inplace=True)

    required_cols = {"roll_no", "amount", "semester"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"File must contain columns: {', '.join(required_cols)}. "
                   f"Found: {', '.join(df.columns)}",
        )

    has_theory = "theory_attendance" in df.columns
    has_practical = "practical_attendance" in df.columns

    inserted = 0
    updated = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        roll_no = str(row["roll_no"]).strip()
        try:
            amount = float(row["amount"])
            semester = int(float(row["semester"]))
        except (ValueError, TypeError) as e:
            errors.append(f"Row {idx + 2}: invalid data — {e}")
            continue

        # Verify student exists
        student = db.query(Student).filter(Student.roll_no == roll_no).first()
        if not student:
            errors.append(f"Row {idx + 2}: student '{roll_no}' not found")
            continue

        # Update attendance if columns are present
        if has_theory:
            try:
                val = float(row["theory_attendance"])
                student.theory_attendance = val
            except (ValueError, TypeError):
                pass
        if has_practical:
            try:
                val = float(row["practical_attendance"])
                student.practical_attendance = val
            except (ValueError, TypeError):
                pass

        existing = (
            db.query(Fine)
            .filter(Fine.roll_no == roll_no, Fine.semester == semester)
            .first()
        )
        if existing:
            # Check if amount changed or became unpaid
            if existing.amount != amount or existing.status != "Unpaid":
                existing.amount = amount
                existing.status = "Unpaid"
                existing.payment_date = None
                existing.transaction_id = None
                updated += 1
                
                # Send email notification for updated fine
                from app.utils.email import send_student_notification, get_html_template
                if student.email:
                    html_content = get_html_template(
                        "Fine Record Updated",
                        f"<p>Dear {student.name},</p><p>Your fine record for Semester {semester} has been updated. The new pending amount is <strong>Rs. {amount}</strong>.</p><p>Please clear your dues as soon as possible via the portal.</p>"
                    )
                    send_student_notification(student.email, "GPH - Fine Record Updated", html_content)
        else:
            new_fine = Fine(
                roll_no=roll_no,
                amount=amount,
                semester=semester,
                status="Unpaid",
            )
            db.add(new_fine)
            inserted += 1
            
            # Send email notification for new fine
            from app.utils.email import send_student_notification, get_html_template
            if student.email:
                html_content = get_html_template(
                    "New Fine Generated",
                    f"<p>Dear {student.name},</p><p>A new fine of <strong>Rs. {amount}</strong> has been generated for Semester {semester}.</p><p>Please log in to the portal to view details and clear your dues.</p>"
                )
                send_student_notification(student.email, "GPH - New Fine Generated", html_content)

    db.commit()

    return FineUploadResponse(
        message="Fine upload processed",
        inserted=inserted,
        updated=updated,
        errors=errors,
    )

def get_overview(db: Session):
    from sqlalchemy import func
    from app.models.fine import Fine
    from app.models.student import Student
    from app.models.request import Request as ClearanceRequest
    
    total_fines = db.query(func.sum(Fine.amount)).filter(Fine.status == "Paid").scalar() or 0.0
    total_students = db.query(func.count(Student.roll_no)).scalar() or 0
    total_branches = db.query(func.count(func.distinct(Student.branch))).scalar() or 0
    total_semesters = db.query(func.count(func.distinct(Student.semester))).scalar() or 0
    pending_requests = db.query(func.count(ClearanceRequest.id)).filter(ClearanceRequest.status == "Pending").scalar() or 0
    
    return {
        "total_fine_collected": float(total_fines),
        "total_students": total_students,
        "total_branches": total_branches,
        "total_semesters": total_semesters,
        "pending_requests": pending_requests
    }

def get_branch_data(department: str, semester: str, db: Session):
    from sqlalchemy import select, func, or_
    from app.models.fine import Fine
    from app.models.student import Student
    
    query = db.query(
        Student.branch,
        Student.semester,
        func.count(func.distinct(Student.roll_no)).label("total_students")
    ).group_by(Student.branch, Student.semester)
    
    if department and department != "all":
        query = query.filter(Student.branch.ilike(f"%{department}%"))
    if semester and semester != "all":
        try:
            query = query.filter(Student.semester == int(semester))
        except ValueError:
            pass
            
    # Convert query to list of dicts with extra lookups
    results = []
    for branch, sem, count in query.all():
        # Get generated fine
        gen_fine = db.query(func.sum(Fine.amount))\
            .join(Student, Student.roll_no == Fine.roll_no)\
            .filter(Student.branch == branch, Student.semester == sem)\
            .scalar() or 0.0
            
        # Get collected fine
        coll_fine = db.query(func.sum(Fine.amount))\
            .join(Student, Student.roll_no == Fine.roll_no)\
            .filter(Student.branch == branch, Student.semester == sem, Fine.status == "Paid")\
            .scalar() or 0.0
            
        # Get defaulters (unpaid fines or unapproved)
        defaulters = db.query(func.count(func.distinct(Student.roll_no)))\
            .join(Fine, Fine.roll_no == Student.roll_no)\
            .filter(Student.branch == branch, Student.semester == sem, Fine.status == "Unpaid")\
            .scalar() or 0
            
        results.append({
            "department": branch,
            "semester": f"{sem}th Semester",
            "total_students": count,
            "total_fine_generated": float(gen_fine),
            "total_fine_collected": float(coll_fine),
            "defaulters": defaulters
        })
    return {"data": results}

def get_global_students(search: str, db: Session):
    from sqlalchemy import or_, func
    from app.models.student import Student
    from app.models.fine import Fine
    
    query = db.query(Student)
    if search:
        query = query.filter(or_(
            Student.name.ilike(f"%{search}%"),
            Student.roll_no.ilike(f"%{search}%")
        ))
    
    students = query.limit(100).all()
    results = []
    for s in students:
        fine_amount = db.query(func.sum(Fine.amount))\
            .filter(Fine.roll_no == s.roll_no, Fine.status == "Unpaid")\
            .scalar() or 0.0
        results.append({
            "roll_no": s.roll_no,
            "name": s.name,
            "department": s.branch or "Unknown",
            "semester": s.semester,
            "theory_attendance": s.theory_attendance,
            "practical_attendance": s.practical_attendance,
            "total_fine": float(fine_amount),
            "status": s.status
        })
    return {"students": results}

def get_attendance_insights(db: Session):
    from sqlalchemy import func
    from app.models.student import Student
    
    rows = db.query(
        Student.branch,
        Student.semester,
        func.avg(Student.theory_attendance).label("avg_theory"),
        func.avg(Student.practical_attendance).label("avg_practical"),
        func.count(Student.roll_no).label("student_count")
    ).group_by(Student.branch, Student.semester).all()
    
    results = []
    for branch, sem, avg_t, avg_p, count in rows:
        results.append({
            "branch": branch or "General",
            "semester": sem,
            "theory_avg": round(float(avg_t or 0), 1),
            "practical_avg": round(float(avg_p or 0), 1),
            "student_count": count
        })
    return {"insights": results}

def get_all_faculty(db: Session):
    from app.models.faculty import Faculty
    faculty = db.query(Faculty).all()
    results = []
    for f in faculty:
        results.append({
            "id": f.id,
            "name": f.name,
            "department": f.branch or "Not Assigned",
            "role": f.role,
            "username": f.username
        })
    return {"faculty": results}

def add_faculty(name, username, password, role, department, gender, db: Session):
    from app.models.faculty import Faculty
    from app.utils.security import hash_password
    
    existing = db.query(Faculty).filter(Faculty.username == username).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    
    hashed = hash_password(password)
    f = Faculty(name=name, username=username, password=hashed, role=role, branch=department, gender=gender)
    db.add(f)
    db.commit()
    return {"message": "Faculty added successfully"}

def update_faculty_role(target_id: int, new_role: str, db: Session):
    from app.models.faculty import Faculty
    faculty = db.query(Faculty).filter(Faculty.id == target_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")
    faculty.role = new_role
    db.commit()
    return {"message": "Role updated"}

def delete_faculty(target_id: int, db: Session):
    from app.models.faculty import Faculty
    faculty = db.query(Faculty).filter(Faculty.id == target_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faculty not found")
    db.delete(faculty)
    db.commit()
    return {"message": "Faculty deleted"}

def upload_admit_cards(file: UploadFile, db: Session):
    import zipfile
    import os
    import io
    from fastapi import HTTPException, status
    
    target_dir = os.path.join("frontend", "static", "admit_cards")
    os.makedirs(target_dir, exist_ok=True)
    
    extracted_count = 0
    try:
        contents = file.file.read()
        with zipfile.ZipFile(io.BytesIO(contents)) as z:
            for info in z.infolist():
                if info.filename.endswith(".pdf"):
                    # Avoid extracting directory paths, just the file
                    basename = os.path.basename(info.filename)
                    if basename:
                        # Extract and save locally
                        extracted_path = os.path.join(target_dir, basename)
                        with open(extracted_path, "wb") as f:
                            f.write(z.read(info.filename))
                        extracted_count += 1
                        
        return {"message": f"Successfully extracted {extracted_count} admit cards."}
    except zipfile.BadZipFile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid ZIP archive.")
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process ZIP: {str(e)}")

def reset_system(db: Session):
    from app.models.fine import Fine
    from app.models.request import Request as ClearanceRequest
    from app.models.student import Student
    
    db.query(ClearanceRequest).delete()
    db.query(Fine).delete()
    db.query(Student).update({"status": "Pending", "theory_attendance": 0.0, "practical_attendance": 0.0})
    db.commit()
    return {"message": "System data has been reset"}

def get_db_insights(db: Session):
    from sqlalchemy import func, Integer
    from app.models.student import Student
    from app.models.faculty import Faculty
    
    rows = db.query(
        Student.branch,
        Student.semester,
        Faculty.name,
        func.count(Student.roll_no).label("student_count")
    ).outerjoin(Faculty, Student.class_incharge_id == Faculty.id)\
    .group_by(Student.branch, Student.semester, Faculty.name).all()
    
    results = []
    for branch, sem, incharge_name, count in rows:
        results.append({
            "branch": branch or "General",
            "semester": sem,
            "incharge_name": incharge_name or "Not Assigned",
            "total_students": count
        })
        
    overall = db.query(
        func.sum(func.cast(Student.ncc, Integer)).label("total_ncc"),
        func.sum(func.cast(Student.hosteller, Integer)).label("total_hosteller"),
        func.sum(func.cast(Student.status == "Pending", Integer)).label("total_pending"),
        func.sum(func.cast(Student.status == "Approved", Integer)).label("total_accepted")
    ).first()
    
    overall_stats = {
        "total_ncc": int(overall.total_ncc or 0),
        "total_hosteller": int(overall.total_hosteller or 0),
        "total_pending": int(overall.total_pending or 0),
        "total_accepted": int(overall.total_accepted or 0)
    }

    return {"overall_stats": overall_stats, "insights": results}
