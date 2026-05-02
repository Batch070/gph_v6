"""SQLAlchemy model for the `requests` table."""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, ForeignKey
from datetime import datetime, timezone
from app.database import Base


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    roll_no = Column(
        String(50),
        ForeignKey("students.roll_no", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    faculty_id = Column(
        Integer,
        ForeignKey("faculty.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        SAEnum("Pending", "Approved", "Rejected", name="request_status"),
        default="Pending",
    )
    note = Column(Text, nullable=True)
    request_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    action_date = Column(DateTime, nullable=True)
