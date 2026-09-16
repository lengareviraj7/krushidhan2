"""
API Route Handlers for Company Profile Settings and Database Backup/Restore.
"""
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from src.api.auth_middleware import get_current_user, require_admin_user
from src.db.connection import get_db_manager
from src.models.system import CompanySettings
from src.repositories.system_repository import SystemRepository
from src.services.backup_service import BackupService

router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/settings")
def get_settings():
    repo = SystemRepository(get_db_manager())
    return repo.get_company_settings()


@router.post("/settings")
def update_settings(settings: CompanySettings, admin: Dict[str, Any] = Depends(require_admin_user)):
    repo = SystemRepository(get_db_manager())
    try:
        repo.update_company_settings(settings)
        return {"success": True, "message": "Settings updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/backup")
def trigger_backup(admin: Dict[str, Any] = Depends(require_admin_user)):
    svc = BackupService(get_db_manager())
    try:
        backup_file = svc.create_backup(backup_type="MANUAL")
        return {"success": True, "file_path": str(backup_file), "filename": backup_file.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backup-history")
def get_backup_history(admin: Dict[str, Any] = Depends(require_admin_user)):
    svc = BackupService(get_db_manager())
    return svc.get_backup_history()

