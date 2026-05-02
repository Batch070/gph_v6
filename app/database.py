"""
SQLAlchemy engine, session factory, and declarative base for MySQL / InnoDB.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# SSL configuration for TiDB Cloud
ssl_args = {}
if "tidbcloud.com" in settings.DATABASE_URL:
    # Try common Linux CA paths (Vercel uses Amazon Linux)
    ca_paths = [
        "/etc/pki/tls/certs/ca-bundle.crt", # Amazon Linux / RHEL
        "/etc/ssl/certs/ca-certificates.crt", # Ubuntu / Debian
        "/etc/ssl/cert.pem" # macOS / Generic
    ]
    ca_path = next((p for p in ca_paths if os.path.exists(p)), None)
    if ca_path:
        ssl_args = {"ssl": {"ca": ca_path}}
    else:
        # Fallback if no file found, at least try to enable SSL
        ssl_args = {"ssl": {}}

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=ssl_args
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
