from sqlalchemy.orm import Session
from app.models.subject import Subject
from typing import List, Optional

def get_subjects(db: Session, semester: Optional[int] = None, branch: Optional[str] = None) -> List[Subject]:
    query = db.query(Subject)
    if semester:
        query = query.filter(Subject.semester == semester)
    if branch:
        query = query.filter(Subject.branch == branch)
    return query.all()

def create_subject(db: Session, semester: int, name: str, group_type: str, subject_code: Optional[str] = None, label: Optional[str] = None, branch: Optional[str] = "Information Technology"):
    if not label:
        suffix = "(T)" if group_type == "Theory" else "(P)"
        code_part = f"({subject_code}) " if subject_code else ""
        label = f"{code_part}{name} {suffix}"
        
    subject = Subject(
        semester=semester,
        name=name,
        group_type=group_type,
        subject_code=subject_code,
        label=label,
        branch=branch
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject

def update_subject(db: Session, subject_id: int, **kwargs):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        return None
    for key, value in kwargs.items():
        if hasattr(subject, key):
            setattr(subject, key, value)
    db.commit()
    db.refresh(subject)
    return subject

def delete_subject(db: Session, subject_id: int):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        return False
    db.delete(subject)
    db.commit()
    return True

def populate_initial_subjects(db: Session):
    # Check if already populated
    if db.query(Subject).count() > 0:
        return
    
    initial_data = [
        # Semester 4 (from existing frontend)
        (4, "PROGRAMMING IN PYTHON", "Theory", "011", "(011) PROGRAMMING IN PYTHON (T)"),
        (4, "PROGRAMMING IN PYTHON", "Lab", "012", "(012) PROGRAMMING IN PYTHON (P)"),
        (4, "DATABASE MANAGEMENT SYSTEM", "Theory", "021", "(021) DATABASE MANAGEMENT SYSTEM (T)"),
        (4, "DATABASE MANAGEMENT SYSTEM", "Lab", "022", "(022) DATABASE MANAGEMENT SYSTEM (P)"),
        (4, "INFORMATION SECURITY", "Theory", "031", "(031) INFORMATION SECURITY (T)"),
        (4, "DATA STRUCTURES", "Theory", "061", "(061) DATA STRUCTURES (T)"),
        (4, "DATA STRUCTURES", "Lab", "062", "(062) DATA STRUCTURES (P)"),
        (4, "ESSENCE OF INDIAN KNOWLEDGE & TRADITION", "Theory", "091", "(091) ESSENCE OF INDIAN KNOWLEDGE & TRADITION (T)"),
        (4, "MINOR PROJECT", "Lab", "102", "(102) MINOR PROJECT (P)"),
        
        # Semester 6 (from user image)
        (6, "ARTIFICIAL INTELLIGENCE & MACHINE LEARNING", "Theory", "011", "(011) ARTIFICIAL INTELLIGENCE & MACHINE LEARNING (T)"),
        (6, "ARTIFICIAL INTELLIGENCE & MACHINE LEARNING", "Lab", "012", "(012) ARTIFICIAL INTELLIGENCE & MACHINE LEARNING (P)"),
        (6, "ENTREPRENEURSHIP AND START UPS", "Theory", "021", "(021) ENTREPRENEURSHIP AND START UPS (T)"),
        (6, "DATA WAREHOUSING AND DATA MINING", "Theory", "231", "(231) DATA WAREHOUSING AND DATA MINING (T)"),
        (6, "BASICS OF MANAGEMENT", "Theory", "301", "(301) BASICS OF MANAGEMENT (T)"),
        (6, "INDIAN CONSTITUTION", "Theory", "351", "(351) INDIAN CONSTITUTION (T)"),
        (6, "MAJOR PROJECT", "Lab", "362", "(362) MAJOR PROJECT (P)"),
    ]
    
    for sem, name, gtype, code, label in initial_data:
        db.add(Subject(
            semester=sem, 
            name=name, 
            group_type=gtype, 
            subject_code=code, 
            label=label,
            branch="Information Technology"
        ))
    db.commit()
