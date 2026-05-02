from sqlalchemy import Column, String, Integer
from app.database import Base

class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
