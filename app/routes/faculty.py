"""Faculty routes — dashboard, update-request."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import TokenData
from app.schemas.faculty import (
    FacultyDashboard,
    UpdateRequestPayload,
    UpdateRequestResponse,
    BulkUpdateRequestPayload,
    BulkUpdateRequestResponse,
)
from app.services import faculty_service
from app.utils.deps import require_role

router = APIRouter(tags=["Faculty"])

_faculty_roles = Depends(
    require_role(
        "ClassIncharge", "HOD", "PTI", "ANO", "HostelSuperintendent_Boys", "HostelSuperintendent_Girls", "Librarian", "CanteenOwner"
    )
)


@router.get("/api/faculty/dashboard", response_model=FacultyDashboard)
def dashboard(
    user: TokenData = _faculty_roles,
    db: Session = Depends(get_db),
):
    return faculty_service.get_dashboard(int(user.sub), db)


@router.post(
    "/api/faculty/update-request/{id}", response_model=UpdateRequestResponse
)
def update_request(
    id: int,
    body: UpdateRequestPayload,
    user: TokenData = _faculty_roles,
    db: Session = Depends(get_db),
):
    return faculty_service.update_request(id, int(user.sub), body.status, body.note, db)

@router.post(
    "/api/faculty/update-requests-bulk", response_model=BulkUpdateRequestResponse
)
def update_requests_bulk(
    body: BulkUpdateRequestPayload,
    user: TokenData = _faculty_roles,
    db: Session = Depends(get_db),
):
    count = faculty_service.bulk_update_requests(body.request_ids, int(user.sub), body.status, db)
    return BulkUpdateRequestResponse(
        message=f"{count} requests updated successfully",
        updated_count=count,
    )
