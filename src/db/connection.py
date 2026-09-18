"""
SQLite Database Connection Manager with WAL mode, foreign keys, and atomic transactions.
Includes cloud persistence for Vercel serverless via MongoDB snapshot save/restore.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, List, Optional, Tuple, Union


class DatabaseManager:
    """Manages SQLite database connections, schema migrations, and transactions."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.bundled_db = base_dir / "data" / "agri_erp.db"
        self._is_vercel = bool(os.environ.get("VERCEL"))
        self._has_mongo = bool(
            os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
        )

        if db_path is not None:
            if isinstance(db_path, str) and db_path == ":memory:":
                self.db_path = ":memory:"
            else:
                self.db_path = Path(db_path)
        elif os.environ.get("DB_PATH"):
            self.db_path = Path(os.environ["DB_PATH"])
        elif self._is_vercel:
            # On Vercel serverless, root filesystem is read-only → use /tmp
            self.db_path = Path("/tmp/agri_erp.db")
            self._provision_vercel_db()
        else:
            # Default to data/agri_erp.db relative to project root
            self.db_path = self.bundled_db

        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _provision_vercel_db(self) -> None:
        """On Vercel cold start, restore from MongoDB snapshot first.
        Falls back to the bundled seed database if no snapshot exists."""
        if self.db_path.exists() and self.db_path.stat().st_size > 100:
            return  # Already provisioned (warm container)

        # Attempt 1: Restore full DB from MongoDB cloud snapshot
        if self._has_mongo:
            try:
                from src.db.cloud_sync import get_cloud_sync_manager
                mgr = get_cloud_sync_manager()
                if mgr.restore_db_snapshot(self.db_path):
                    return  # Success — full database restored from cloud
            except Exception:
                pass

        # Attempt 2: Copy bundled seed database
        if self.bundled_db.exists() and self.bundled_db.stat().st_size > 0:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(self.bundled_db), str(self.db_path))
            except Exception:
                pass

    def _create_raw_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        
        # Configure SQLite pragmas for maximum integrity & offline desktop performance
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.execute("PRAGMA busy_timeout = 10000;")
        cursor.close()
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = self._create_raw_connection()
        
        # Auto-verify that essential tables exist; if not, initialize schema + seed
        if self.db_path != ":memory:":
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='products' LIMIT 1;")
                has_tables = cur.fetchone()
                cur.close()
                if not has_tables:
                    conn.close()
                    self.initialize_database(include_seed=True)
                    conn = self._create_raw_connection()
            except Exception:
                pass

        return conn

    def initialize_database(self, include_seed: bool = True) -> None:
        """Runs the schema DDL and optional seed data on the database."""
        current_dir = Path(__file__).resolve().parent
        schema_file = current_dir / "schema.sql"
        seed_file = current_dir / "seed.sql"

        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found at {schema_file}")

        conn = self._create_raw_connection()
        try:
            cursor = conn.cursor()
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            cursor.executescript(schema_sql)

            if include_seed and seed_file.exists():
                with open(seed_file, "r", encoding="utf-8") as f:
                    seed_sql = f.read()
                cursor.executescript(seed_sql)
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    def _save_cloud_snapshot(self) -> None:
        """After a successful write, push the full DB file to MongoDB (async)."""
        if not (self._is_vercel and self._has_mongo):
            return
        if self.db_path == ":memory:":
            return
        try:
            from src.db.cloud_sync import get_cloud_sync_manager
            mgr = get_cloud_sync_manager()
            if mgr.is_cloud_enabled:
                mgr.save_db_snapshot_async(Path(self.db_path))
        except Exception:
            pass

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Atomic transaction context manager. Commits on success, rolls back on error."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        # After connection is closed (WAL flushed), persist to cloud
        self._save_cloud_snapshot()

    def execute_query(self, sql: str, params: Union[Tuple, List] = ()) -> int:
        """Execute an INSERT, UPDATE, or DELETE query and return the lastrowid or rowcount."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid or cursor.rowcount

    def fetch_one(self, sql: str, params: Union[Tuple, List] = ()) -> Optional[sqlite3.Row]:
        """Fetch a single record as sqlite3.Row."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Union[Tuple, List] = ()) -> List[sqlite3.Row]:
        """Fetch all matching records as a list of sqlite3.Row."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            conn.close()

    def check_integrity(self) -> List[str]:
        """Runs SQLite PRAGMA integrity_check and returns results (e.g. ['ok'])."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            rows = cursor.fetchall()
            return [str(r[0]) for r in rows if r]
        finally:
            conn.close()

    def check_foreign_keys(self) -> List[Tuple[Any, ...]]:
        """Runs SQLite PRAGMA foreign_key_check and returns constraint violation tuples."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_key_check;")
            rows = cursor.fetchall()
            return [tuple(r) for r in rows]
        finally:
            conn.close()

    def get_schema_version(self) -> int:
        """Returns the current database schema version from schema_version table."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version' LIMIT 1;")
            if not cursor.fetchone():
                return 0
            cursor.execute("SELECT MAX(version_number) FROM schema_version;")
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            return 0
        finally:
            conn.close()



# Default singleton instance for convenience
_default_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_path: Optional[Union[str, Path]] = None) -> DatabaseManager:
    """Get or create the global DatabaseManager instance."""
    global _default_db_manager
    if db_path is not None:
        return DatabaseManager(db_path)
    if _default_db_manager is None:
        _default_db_manager = DatabaseManager()
    return _default_db_manager


@contextmanager
def transaction(db_path: Optional[Union[str, Path]] = None) -> Generator[sqlite3.Connection, None, None]:
    """Shortcut context manager for transactions using the default or specified database."""
    manager = get_db_manager(db_path)
    with manager.transaction() as conn:
        yield conn
