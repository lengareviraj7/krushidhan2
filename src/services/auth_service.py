"""
Service Layer for User Authentication, Role-Based Access, and Cryptographic Session Tokens.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, List, Optional
from src.db.connection import DatabaseManager, get_db_manager
from src.models.system import User
from src.repositories.system_repository import SystemRepository

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

JWT_SECRET = os.environ.get("JWT_SECRET", "krushidhan_erp_secure_key_2026_akash_lengare_9503673620")
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


class AuthService:
    """User authentication, role-based checks, cryptographic tokens, and secure password management."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
        self.system_repo = SystemRepository(self.db)
        self.ensure_bootstrap_users()

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt if available or salted SHA-256 fallback."""
        if HAS_BCRYPT:
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        else:
            salt = "krushidhan_agri_erp_salt_2026"
            return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hashed password."""
        if not plain_password or not hashed_password:
            return False

        if HAS_BCRYPT and hashed_password.startswith("$2b$"):
            try:
                if bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8")):
                    return True
            except Exception:
                pass

        # SHA-256 check or fallback compatibility for initial default passwords
        salt = "krushidhan_agri_erp_salt_2026"
        expected = hashlib.sha256(f"{salt}{plain_password}".encode("utf-8")).hexdigest()
        if expected == hashed_password:
            return True

        old_salt = "offline_agri_erp_salt"
        expected_old = hashlib.sha256(f"{old_salt}{plain_password}".encode("utf-8")).hexdigest()
        if expected_old == hashed_password:
            return True

        return False



    @staticmethod
    def create_access_token(user_id: int, username: str, full_name: str, role: str, expires_in: int = DEFAULT_TOKEN_EXPIRY_SECONDS) -> str:
        """Generate an HMAC-SHA256 cryptographically signed JWT session token."""
        header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "role": role,
            "iat": now,
            "exp": now + expires_in,
        }

        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}"

        signature = hmac.new(
            JWT_SECRET.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        sig_b64 = _b64url_encode(signature)

        return f"{signing_input}.{sig_b64}"

    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify cryptographic HMAC-SHA256 signature and expiration of JWT token."""
        if not token or "." not in token:
            return None

        parts = token.strip().split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        expected_sig = hmac.new(
            JWT_SECRET.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        try:
            actual_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None

            payload_bytes = _b64url_decode(payload_b64)
            payload = json.loads(payload_bytes.decode("utf-8"))

            exp = payload.get("exp", 0)
            if time.time() > exp:
                return None  # Token expired

            return payload
        except Exception:
            return None

    def ensure_bootstrap_users(self) -> None:
        """Ensure initial Admin users exist in database."""
        try:
            users = self.system_repo.list_users()
            if not users:
                default_hash = self.hash_password("krushidhan@2026")
                self.system_repo.create_user(
                    User(
                        username="admin",
                        password_hash=default_hash,
                        full_name="आकाश लेंगारे (Admin)",
                        role="ADMIN",
                        is_active=1,
                    )
                )
                self.system_repo.create_user(
                    User(
                        username="akash",
                        password_hash=default_hash,
                        full_name="आकाश लेंगारे",
                        role="ADMIN",
                        is_active=1,
                    )
                )
                self.system_repo.create_user(
                    User(
                        username="billing",
                        password_hash=self.hash_password("billing123"),
                        full_name="Counter Staff",
                        role="OPERATOR",
                        is_active=1,
                    )
                )
        except Exception:
            pass

    def authenticate_user(self, username: str, plain_password: str) -> Optional[User]:
        """Authenticate user by username and password."""
        user = self.system_repo.get_user_by_username(username.strip().lower())
        if not user or user.is_active != 1:
            return None

        if self.verify_password(plain_password, user.password_hash or ""):
            return user
        return None

    def register_user(self, username: str, plain_password: str, full_name: str, role: str = "OPERATOR") -> int:
        """Create new system user with hashed password."""
        existing = self.system_repo.get_user_by_username(username.strip().lower())
        if existing:
            raise ValueError(f"User with username '{username}' already exists.")

        hashed = self.hash_password(plain_password)
        user = User(
            username=username.strip().lower(),
            password_hash=hashed,
            full_name=full_name.strip(),
            role=role.upper(),
            is_active=1,
        )
        return self.system_repo.create_user(user)

    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change password with verification of old password."""
        user = self.system_repo.get_user_by_id(user_id)
        if not user:
            return False

        if not self.verify_password(old_password, user.password_hash or ""):
            return False

        new_hash = self.hash_password(new_password)
        self.system_repo.update_user_password(user_id, new_hash)
        return True

    def reset_password_by_admin(self, target_user_id: int, new_password: str) -> bool:
        """Admin override reset password."""
        user = self.system_repo.get_user_by_id(target_user_id)
        if not user:
            return False

        new_hash = self.hash_password(new_password)
        self.system_repo.update_user_password(target_user_id, new_hash)
        return True

    def list_users(self) -> List[User]:
        """List all active and inactive users."""
        return self.system_repo.list_users()

    def set_user_active_status(self, user_id: int, is_active: bool) -> None:
        """Activate or deactivate user account."""
        self.system_repo.update_user_status(user_id, 1 if is_active else 0)
