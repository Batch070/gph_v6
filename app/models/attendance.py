"""SQLAlchemy model for the `subject_attendance` table."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SAEnum, ForeignKey
from app.database import Base


class SubjectAttendance(Base):
    __tablename__ = "subject_attendance"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    roll_no = Column(
        String(50),
        nullable=False,
        index=True,
    )
    student_name = Column(String(100), nullable=True)
    semester = Column(Integer, nullable=False)
    subject_name = Column(String(100), nullable=False)
    group_type = Column(
        SAEnum("Theory", "Lab", name="group_type_enum"),
        nullable=False,
    )
    total_classes = Column(Integer, nullable=False, default=0)
    attended_classes = Column(Integer, nullable=False, default=0)
    uploaded_by = Column(Integer, ForeignKey("faculty.id"), nullable=True)
    upload_session_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
