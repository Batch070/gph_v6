"""SQLAlchemy model for the `fines` table."""

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SAEnum, ForeignKey
from app.database import Base


class Fine(Base):
    __tablename__ = "fines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    roll_no = Column(
        String(50),
        ForeignKey("students.roll_no", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = Column(Float, nullable=False, default=0.0)
    semester = Column(Integer, nullable=False)
    status = Column(
        SAEnum("Unpaid", "Paid", name="fine_status"),
        default="Unpaid",
    )
    payment_date = Column(DateTime, nullable=True)
    transaction_id = Column(String(100), nullable=True)
