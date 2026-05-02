from pydantic import BaseModel
from typing import Optional

class BranchBase(BaseModel):
    name: str

class BranchCreate(BranchBase):
    hod_name: str
    hod_username: str
    hod_password: str

class BranchResponse(BranchBase):
    id: int

    class Config:
        from_attributes = True
