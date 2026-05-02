"""SQLAlchemy model for the `students` table."""

from sqlalchemy import Column, String, Integer, Float, Boolean, Date, Enum as SAEnum
from sqlalchemy.orm import validates
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    roll_no = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    branch = Column(String(100), default="Information Technology")
    semester = Column(Integer, nullable=False)
    academic_year = Column(String(20), nullable=False)
    dob = Column(Date, nullable=False)
    email = Column(String(100), nullable=True)
    gender = Column(String(20), nullable=True)  # Added to match DB
    ncc = Column(Boolean, default=False)
    hosteller = Column(Boolean, default=False)
    practical_attendance = Column(Float, default=0.0)
    theory_attendance = Column(Float, default=0.0)
    class_incharge_id = Column(Integer, nullable=True)
    hod_id = Column(Integer, nullable=True)
    status = Column(
        SAEnum("Pending", "Approved", "Cleared", name="student_status"),
        default="Pending",
    )

    @validates("email")
    def convert_lower(self, key, value):
        if value is not None:
            return value.strip().lower()
        return value
