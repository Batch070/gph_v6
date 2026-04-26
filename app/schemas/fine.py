"""Pydantic schemas for fine-related admin endpoints."""

from pydantic import BaseModel


class FineUploadResponse(BaseModel):
    message: str
    inserted: int
    updated: int
    errors: list[str] = []
