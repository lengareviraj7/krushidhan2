"""
Automated Pytest Suite for Phase 1: Authentication, Authorization, RBAC, and Security Hardening.
Tests master password removal, password hashing, JWT session verification, route authorization, and RBAC.
"""
import pytest
from fastapi.testclient import TestClient
from src.app import app
from src.db.connection import DatabaseManager
from src.repositories.system_repository import SystemRepository
from src.services.auth_service import AuthService

client = TestClient(app)


@pytest.fixture
def test_db_manager(tmp_path):
    """Fixture to provide an isolated temporary database for testing."""
    db_file = tmp_path / "test_auth_security.db"
    db_mgr = DatabaseManager(db_file)
    db_mgr.initialize_database(include_seed=True)
    return db_mgr


def test_master_password_bypass_removed(test_db_manager):
    """Verify that hardcoded master passwords CANNOT bypass authentication for arbitrary accounts."""
    auth_svc = AuthService(test_db_manager)

    # Register a test user with a custom unique password
    auth_svc.register_user(
        username="test_operator",
        plain_password="SecretPassword#2026",
        full_name="Test Operator",
        role="OPERATOR",
    )

    # 1. Valid authentication with correct password MUST succeed
    user = auth_svc.authenticate_user("test_operator", "SecretPassword#2026")
    assert user is not None
    assert user.username == "test_operator"

    # 2. Attempts to log in using hardcoded master passwords MUST FAIL for this account
    assert auth_svc.authenticate_user("test_operator", "krushidhan@2026") is None
    assert auth_svc.authenticate_user("test_operator", "admin123") is None
    assert auth_svc.authenticate_user("test_operator", "akash@2026") is None
    assert auth_svc.authenticate_user("test_operator", "wrong_password") is None


def test_password_hashing_security():
    """Verify password hashing generates non-plaintext cryptographic hashes."""
    plain = "AgriERP@2026"
    hashed = AuthService.hash_password(plain)

    # Hash must not contain plaintext password
    assert plain not in hashed
    # Password verification must return True for correct password and False for incorrect password
    assert AuthService.verify_password(plain, hashed) is True
    assert AuthService.verify_password("WrongPass", hashed) is False
    assert AuthService.verify_password("", hashed) is False


def test_jwt_token_generation_and_verification():
    """Verify HMAC-SHA256 JWT access token generation, payload verification, and tamper rejection."""
    token = AuthService.create_access_token(
        user_id=101,
        username="akash_admin",
        full_name="Akash Lengare",
        role="ADMIN",
        expires_in=3600,
    )

    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    # Verification must extract correct payload
    payload = AuthService.verify_access_token(token)
    assert payload is not None
    assert payload["user_id"] == 101
    assert payload["username"] == "akash_admin"
    assert payload["role"] == "ADMIN"

    # Tampered token must be rejected
    tampered_token = token[:-5] + "XXXXX"
    assert AuthService.verify_access_token(tampered_token) is None


def test_protected_routes_require_authentication():
    """Verify protected API routes return HTTP 401 Unauthorized when no auth token is provided."""
    # Attempting to fetch admin user list without auth header
    res_users = client.get("/api/auth/users")
    assert res_users.status_code == 401

    # Attempting to update settings without auth header
    res_settings = client.post("/api/system/settings", json={"company_name": "Hackers Ltd"})
    assert res_settings.status_code == 401

    # Attempting to trigger backup without auth header
    res_backup = client.post("/api/system/backup")
    assert res_backup.status_code == 401


def test_rbac_enforcement():
    """Verify Role-Based Access Control blocks non-admin users from admin-only endpoints."""
    # Create operator token
    op_token = AuthService.create_access_token(
        user_id=202,
        username="counter_staff",
        full_name="Counter Operator",
        role="OPERATOR",
    )
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Operator calling admin-only endpoint MUST receive 403 Forbidden
    res_users = client.get("/api/auth/users", headers=op_headers)
    assert res_users.status_code == 403

    res_settings = client.post("/api/system/settings", json={"company_name": "Test"}, headers=op_headers)
    assert res_settings.status_code == 403

    # Create admin token
    admin_token = AuthService.create_access_token(
        user_id=1,
        username="admin",
        full_name="Admin User",
        role="ADMIN",
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin calling admin-only endpoint MUST succeed (200 OK)
    res_users_admin = client.get("/api/auth/users", headers=admin_headers)
    assert res_users_admin.status_code == 200
    assert isinstance(res_users_admin.json(), list)
