"""SQLAlchemy model for the `faculty` table."""

from sqlalchemy import Column, Integer, String, Enum as SAEnum
from app.database import Base


class Faculty(Base):
    __tablename__ = "faculty"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=True)  # Added to support honorifics
    role = Column(
        SAEnum(
            "ClassIncharge",
            "HOD",
            "PTI",
            "ANO",
            "HostelSuperintendent_Boys",
            "HostelSuperintendent_Girls",
            "Librarian",
            "CanteenOwner",
            "Admin",
            name="faculty_role",
        ),
        nullable=False,
    )
    branch = Column(String(100), nullable=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
