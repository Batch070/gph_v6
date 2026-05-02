"""
SQLAlchemy engine, session factory, and declarative base for MySQL / InnoDB.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# SSL configuration for TiDB Cloud (Serverless)
connect_args = {}
if "tidbcloud.com" in settings.DATABASE_URL:
    # Most reliable way on Vercel: let the driver handle TLS auto-negotiation
    connect_args = {
        "ssl": {
            "ca": None, # Use system defaults
            "check_hostname": False # Avoid hostname mismatch issues in serverless
        }
    }

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300 # Reset connections every 5 mins
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and closes it on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
