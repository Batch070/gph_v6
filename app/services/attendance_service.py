"""
Business logic for attendance image upload, storage, aggregation, and fine calculation.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, UploadFile, status, BackgroundTasks

from app.models.attendance import SubjectAttendance
from app.models.student import Student
from app.models.fine import Fine
from app.models.faculty import Faculty
from app.services.email_service import send_attendance_report
from app.services import attendance_ai_service


# ── AI Register Processing ────────────────────────────────────
def process_register_image(
    file: UploadFile,
    semester: int,
    subject_name: str,
    group_type: str,
    total_classes: int,
    faculty_id: int,
    db: Session,
) -> dict:
    """
    1. Verify faculty.
    2. Extract data via AI.
    3. Match extracted Roll Nos. with DB students for this semester.
    4. Save extracted records logic.
    """
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Faculty not found")

    image_bytes = file.file.read()
    
    # Check for duplicate subject upload
    existing = (
        db.query(SubjectAttendance)
        .filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.subject_name == subject_name,
            SubjectAttendance.group_type == group_type,
            SubjectAttendance.uploaded_by == faculty_id,
        )
        .first()
    )
    if existing:
        db.query(SubjectAttendance).filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.subject_name == subject_name,
            SubjectAttendance.group_type == group_type,
            SubjectAttendance.uploaded_by == faculty_id,
        ).delete(synchronize_session=False)
        db.flush()

    extracted_data = attendance_ai_service.extract_attendance_from_image(image_bytes, total_classes)

    db_students = (
        db.query(Student)
        .filter(Student.semester == semester)
        .all()
    )
    # Map lowercase student name to the actual Student object for robust matching
    student_obj_map = {s.name.strip().lower(): s for s in db_students}

    session_id = str(uuid.uuid4())[:8]
    stored_count = 0
    students_res = []

    for item in extracted_data:
        extracted_name = str(item.get("student_name", "")).strip()
        extracted_name_lower = extracted_name.lower()
        attended = item.get("attended_classes", 0)

        # Skip rows that AI invented if they aren't real students in this semester
        if extracted_name_lower not in student_obj_map:
            continue

        attended = max(0, min(attended, total_classes))
        matched_student = student_obj_map[extracted_name_lower]
        roll_no = matched_student.roll_no
        actual_name = matched_student.name

        record = SubjectAttendance(
            roll_no=roll_no,
            student_name=actual_name,
            semester=semester,
            subject_name=subject_name,
            group_type=group_type,
            total_classes=total_classes,
            attended_classes=attended,
            uploaded_by=faculty_id,
            upload_session_id=session_id,
            created_at=datetime.utcnow(),
        )
        db.add(record)
        stored_count += 1

        students_res.append({
            "roll_no": roll_no,
            "name": actual_name,
            "total_classes": total_classes,
            "attended_classes": attended,
            "absent_classes": total_classes - attended,
        })

    db.commit()

    return {
        "message": f"Successfully extracted {stored_count} records",
        "subject_name": subject_name,
        "group_type": group_type,
        "total_classes": total_classes,
        "students": students_res,
        "upload_session_id": session_id,
    }



# ── Manual Data Entry ─────────────────────────────────────────
def process_manual_attendance(
    semester: int,
    subject_name: str,
    group_type: str,
    total_classes: int,
    students: list,
    faculty_id: int,
    db: Session,
) -> dict:
    """
    Process manual data entry for class attendance:
    1. Parse submitted grid
    2. Overwrite existing records for the subject/semester
    3. Store them in SubjectAttendance
    """
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Faculty not found")

    # Check for duplicate subject upload
    existing = (
        db.query(SubjectAttendance)
        .filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.subject_name == subject_name,
            SubjectAttendance.group_type == group_type,
            SubjectAttendance.uploaded_by == faculty_id,
        )
        .first()
    )
    if existing:
        # Delete old data for this subject to allow re-entry
        db.query(SubjectAttendance).filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.subject_name == subject_name,
            SubjectAttendance.group_type == group_type,
            SubjectAttendance.uploaded_by == faculty_id,
        ).delete(synchronize_session=False)
        db.flush()

    # Generate session ID just to maintain db consistency
    session_id = str(uuid.uuid4())[:8]

    # Store attendance records
    stored_count = 0
    students_data = []

    for student_record in students:
        roll_no = student_record.roll_no.strip()
        name = student_record.student_name.strip()
        attended = student_record.attended_classes

        # Clamp attended to not exceed total and to be at least 0
        attended = max(0, min(attended, total_classes))

        record = SubjectAttendance(
            roll_no=roll_no,
            student_name=name,
            semester=semester,
            subject_name=subject_name,
            group_type=group_type,
            total_classes=total_classes,
            attended_classes=attended,
            uploaded_by=faculty_id,
            upload_session_id=session_id,
            created_at=datetime.utcnow(),
        )
        db.add(record)
        stored_count += 1

        students_data.append({
            "roll_no": roll_no,
            "name": name,
            "total_classes": total_classes,
            "attended_classes": attended,
            "absent_classes": total_classes - attended,
        })

    db.commit()

    return {
        "message": f"Successfully submitted data for '{subject_name}' ({group_type})",
        "session_id": session_id,
        "subject_name": subject_name,
        "group_type": group_type,
        "total_classes": total_classes,
        "students_count": stored_count,
        "students": students_data,
    }


# ── List Uploaded Subjects ───────────────────────────────────
def get_uploaded_subjects(semester: int, faculty_id: int, db: Session) -> list[dict]:
    """Get all subjects that have been uploaded for a semester by this faculty."""
    subjects = (
        db.query(
            SubjectAttendance.subject_name,
            SubjectAttendance.group_type,
            func.count(SubjectAttendance.id).label("student_count"),
            func.max(SubjectAttendance.total_classes).label("total_classes"),
            func.max(SubjectAttendance.created_at).label("uploaded_at"),
        )
        .filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.uploaded_by == faculty_id,
        )
        .group_by(SubjectAttendance.subject_name, SubjectAttendance.group_type)
        .all()
    )

    return [
        {
            "subject_name": s.subject_name,
            "group_type": s.group_type,
            "student_count": s.student_count,
            "total_classes": s.total_classes,
            "uploaded_at": str(s.uploaded_at) if s.uploaded_at else None,
        }
        for s in subjects
    ]


# ── Get Subject Detail ───────────────────────────────────────
def get_subject_detail(
    semester: int, subject_name: str, group_type: str, faculty_id: int, db: Session
) -> list[dict]:
    """Get individual student records for a specific subject."""
    records = (
        db.query(SubjectAttendance)
        .filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.subject_name == subject_name,
            SubjectAttendance.group_type == group_type,
            SubjectAttendance.uploaded_by == faculty_id,
        )
        .all()
    )

    return [
        {
            "id": r.id,
            "roll_no": r.roll_no,
            "student_name": r.student_name,
            "total_classes": r.total_classes,
            "attended_classes": r.attended_classes,
            "absent_classes": r.total_classes - r.attended_classes,
        }
        for r in records
    ]


# ── Delete Subject ───────────────────────────────────────────
def delete_subject(
    semester: int, subject_name: str, group_type: str, faculty_id: int, db: Session
) -> dict:
    """Delete all records for a specific subject."""
    count = (
        db.query(SubjectAttendance)
        .filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.subject_name == subject_name,
            SubjectAttendance.group_type == group_type,
            SubjectAttendance.uploaded_by == faculty_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "message": f"Deleted {count} records for '{subject_name}' ({group_type})",
        "deleted_count": count,
    }


# ── Update Extracted Records ─────────────────────────────────
def update_subject_records(updates: list, faculty_id: int, db: Session) -> dict:
    """Update previously extracted student records (fixing AI failures)."""
    updated_count = 0
    for update in updates:
        record = db.query(SubjectAttendance).filter(
            SubjectAttendance.id == update.id,
            SubjectAttendance.uploaded_by == faculty_id
        ).first()

        if record:
            record.roll_no = update.roll_no
            record.student_name = update.student_name
            record.total_classes = update.total_classes
            record.attended_classes = update.attended_classes
            updated_count += 1
    
    db.commit()
    return {
        "message": f"Successfully updated {updated_count} records",
        "updated_count": updated_count
    }


# ── Aggregated Student Summary ───────────────────────────────
def get_student_summary(semester: int, faculty_id: int, db: Session) -> list[dict]:
    """
    Aggregate attendance across all uploaded subjects for each student.
    Returns per-student totals for theory and lab.
    """
    records = (
        db.query(SubjectAttendance)
        .filter(
            SubjectAttendance.semester == semester,
            SubjectAttendance.uploaded_by == faculty_id,
        )
        .all()
    )

    # Aggregate per student
    student_map = {}  # roll_no -> { ... }

    for r in records:
        key = r.roll_no
        if key not in student_map:
            student_map[key] = {
                "roll_no": r.roll_no,
                "name": r.student_name or "",
                "total_theory": 0,
                "attended_theory": 0,
                "total_lab": 0,
                "attended_lab": 0,
            }

        entry = student_map[key]
        if r.group_type == "Theory":
            entry["total_theory"] += r.total_classes
            entry["attended_theory"] += r.attended_classes
        else:  # Lab
            entry["total_lab"] += r.total_classes
            entry["attended_lab"] += r.attended_classes

    # Compute derived fields
    result = []
    for roll_no, data in student_map.items():
        absent_theory = data["total_theory"] - data["attended_theory"]
        absent_lab = data["total_lab"] - data["attended_lab"]
        total_classes = data["total_theory"] + data["total_lab"]
        total_attended = data["attended_theory"] + data["attended_lab"]
        fine = (absent_theory + absent_lab) * 5
        theory_pct = round((data["attended_theory"] / data["total_theory"] * 100), 2) if data["total_theory"] > 0 else 0
        lab_pct = round((data["attended_lab"] / data["total_lab"] * 100), 2) if data["total_lab"] > 0 else 0

        result.append({
            **data,
            "absent_theory": absent_theory,
            "absent_lab": absent_lab,
            "total_classes": total_classes,
            "total_attended": total_attended,
            "fine": fine,
            "theory_percentage": theory_pct,
            "lab_percentage": lab_pct,
        })

    # Sort by roll number
    result.sort(key=lambda x: x["roll_no"])
    return result


# ── Finalize & Calculate Fines ───────────────────────────────
def finalize_attendance(semester: int, faculty_id: int, db: Session, background_tasks: BackgroundTasks) -> dict:
    """
    Finalize attendance for a semester:
    1. Aggregate all subjects
    2. Calculate fines: (absent_theory + absent_lab) × 5
    3. Update student records with attendance percentages
    4. Create/update fine records in the fines table
    """
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Faculty not found")

    summary = get_student_summary(semester, faculty_id, db)

    if not summary:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No attendance data found. Please upload subject registers first.",
        )

    updated_students = 0
    fines_created = 0
    fines_updated = 0
    total_fine_amount = 0

    for student_data in summary:
        roll_no = student_data["roll_no"]
        fine_amount = student_data["fine"]
        theory_pct = (
            round(student_data["attended_theory"] / student_data["total_theory"] * 100, 2)
            if student_data["total_theory"] > 0
            else 0
        )
        practical_pct = (
            round(student_data["attended_lab"] / student_data["total_lab"] * 100, 2)
            if student_data["total_lab"] > 0
            else 0
        )

        # Update student record
        student = db.query(Student).filter(Student.roll_no == roll_no).first()
        if student:
            student.theory_attendance = theory_pct
            student.practical_attendance = practical_pct
            updated_students += 1
            
            # Queue the email
            background_tasks.add_task(
                send_attendance_report,
                student_email=student.email,
                student_name=student.name,
                semester=semester,
                theory_pct=theory_pct,
                practical_pct=practical_pct,
                fine=fine_amount
            )

        # Create or update fine record
        existing_fine = (
            db.query(Fine)
            .filter(Fine.roll_no == roll_no, Fine.semester == semester)
            .first()
        )

        if existing_fine:
            existing_fine.amount = fine_amount
            fines_updated += 1
        else:
            new_fine = Fine(
                roll_no=roll_no,
                amount=fine_amount,
                semester=semester,
                status="Unpaid",
            )
            db.add(new_fine)
            fines_created += 1

        total_fine_amount += fine_amount

    db.commit()

    return {
        "message": f"Attendance finalized for Semester {semester}",
        "students_updated": updated_students,
        "fines_created": fines_created,
        "fines_updated": fines_updated,
        "total_fine_amount": total_fine_amount,
        "student_count": len(summary),
    }
