from typing import Optional
"""FastAPI dependencies for JWT auth and role-based access control."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.utils.security import decode_access_token
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/faculty/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Extract and validate the JWT, returning TokenData (sub + role)."""
    payload = decode_access_token(token)
    sub: Optional[str] = payload.get("sub")
    role: Optional[str] = payload.get("role")
    if sub is None or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return TokenData(sub=sub, role=role)


def require_role(*allowed_roles: str):
    """Dependency factory: only lets users with one of `allowed_roles` through."""

    def _checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}",
            )
        return current_user

    return _checker
