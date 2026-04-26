"""Pydantic schemas for authentication (login / JWT tokens)."""

from pydantic import BaseModel


# ── Student Login ─────────────────────────────────────────────
class StudentLoginRequest(BaseModel):
    roll_no: str
    dob: str  # expected format: YYYY-MM-DD


# ── Faculty Login ─────────────────────────────────────────────
class FacultyLoginRequest(BaseModel):
    username: str
    password: str


# ── JWT Token ─────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    sub: str
    role: str
