"""SQLAlchemy model for the `subjects` table."""

from sqlalchemy import Column, Integer, String, Enum as SAEnum
from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    semester = Column(Integer, nullable=False, index=True)
    subject_code = Column(String(20), nullable=True)
    name = Column(String(100), nullable=False)
    group_type = Column(
        SAEnum("Theory", "Lab", name="subject_group_type_enum"),
        nullable=False,
    )
    label = Column(String(150), nullable=True)  # Full label like "(011) PYTHON (T)"
    branch = Column(String(100), nullable=True, default="Information Technology")
