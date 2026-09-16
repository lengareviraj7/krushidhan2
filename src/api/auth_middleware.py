"""
FastAPI Authentication Dependencies and Security Middleware.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import Header, HTTPException, Request, status
from src.services.auth_service import AuthService


def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract Bearer token from Authorization header or cookie."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing. Please log in to Krushidhan ERP.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.strip().split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization.strip()


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency that verifies JWT token and returns authenticated user payload."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Access to Krushidhan ERP requires login.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = get_token_from_header(authorization)
    payload = AuthService.verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_admin_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency that enforces ADMIN / OWNER permissions."""
    user = get_current_user(authorization)
    role = (user.get("role") or "").upper()
    if role not in ("ADMIN", "OWNER", "SUPERADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Owner / Admin privileges required for this module.",
        )
    return user


def require_roles(allowed_roles: list[str]):
    """Flexible RBAC dependency factory to check user roles."""
    def role_checker(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
        user = get_current_user(authorization)
        role = (user.get("role") or "").upper()
        normalized_allowed = [r.upper() for r in allowed_roles]
        if "ADMIN" not in normalized_allowed and "OWNER" not in normalized_allowed:
            normalized_allowed.extend(["ADMIN", "OWNER", "SUPERADMIN"])
        if role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: required role in {allowed_roles}.",
            )
        return user
    return role_checker

