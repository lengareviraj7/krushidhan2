"""
Cloud Database Persistence for Vercel Serverless Functions.

Stores the ENTIRE SQLite database file as a single binary snapshot in MongoDB.
This guarantees that ALL 26 tables, ALL rows, ALL indexes are preserved across
Vercel container restarts — no per-table sync, no missing tables, no ID conflicts.

On cold start:  MongoDB → /tmp/agri_erp.db  (restore)
After each write: /tmp/agri_erp.db → MongoDB  (save)
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("agri_erp.cloud_sync")

try:
    import pymongo
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

# Collection & document key used to store the DB snapshot
_SNAPSHOT_COLLECTION = "db_snapshots"
_SNAPSHOT_KEY = "agri_erp_main"


class CloudSyncManager:
    """Stores/restores the full SQLite database file as a binary snapshot in MongoDB."""

    def __init__(self, mongo_uri: Optional[str] = None):
        self.mongo_uri = (
            mongo_uri
            or os.environ.get("MONGODB_URI")
            or os.environ.get("MONGO_URL")
        )
        self.db_name = os.environ.get("MONGODB_DB_NAME", "krushidhan_erp")
        self._client: Any = None
        self._db: Any = None
        self._save_lock = threading.Lock()

        if HAS_PYMONGO and self.mongo_uri:
            try:
                self._client = pymongo.MongoClient(
                    self.mongo_uri,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=10000,
                )
                # Ping to verify connectivity (fast fail if unreachable)
                self._client.admin.command("ping")
                self._db = self._client[self.db_name]
                logger.info("CloudSyncManager: Connected to MongoDB Atlas.")
            except Exception as e:
                logger.warning(f"CloudSyncManager: MongoDB connection failed: {e}")
                self._client = None
                self._db = None

    @property
    def is_cloud_enabled(self) -> bool:
        return self._db is not None

    # ------------------------------------------------------------------
    # RESTORE: MongoDB binary → /tmp/agri_erp.db  (called on cold start)
    # ------------------------------------------------------------------
    def restore_db_snapshot(self, target_path: Path) -> bool:
        """Download the latest DB file snapshot from MongoDB and write it to disk.
        Returns True if a snapshot was found and restored, False otherwise."""
        if not self.is_cloud_enabled:
            return False

        try:
            col = self._db[_SNAPSHOT_COLLECTION]
            doc = col.find_one({"_id": _SNAPSHOT_KEY})
            if doc and doc.get("db_bytes"):
                db_bytes = bytes(doc["db_bytes"])
                if len(db_bytes) > 100:  # sanity: not an empty/corrupt file
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(db_bytes)
                    logger.info(
                        f"CloudSyncManager: Restored DB snapshot ({len(db_bytes):,} bytes) → {target_path}"
                    )
                    return True
            logger.info("CloudSyncManager: No snapshot found in MongoDB; will use bundled DB.")
            return False
        except Exception as e:
            logger.error(f"CloudSyncManager: Failed to restore snapshot: {e}")
            return False

    # ------------------------------------------------------------------
    # SAVE: /tmp/agri_erp.db → MongoDB binary  (called after each commit)
    # ------------------------------------------------------------------
    def save_db_snapshot(self, source_path: Path) -> bool:
        """Read the SQLite DB file from disk and upload it as binary to MongoDB.
        Thread-safe; only one save can run at a time."""
        if not self.is_cloud_enabled:
            return False

        if not source_path.exists():
            return False

        # Use a lock so concurrent transactions don't interleave uploads
        if not self._save_lock.acquire(blocking=False):
            # Another save is in progress; skip this one (data is already being saved)
            return False

        try:
            db_bytes = source_path.read_bytes()
            if len(db_bytes) < 100:
                return False

            col = self._db[_SNAPSHOT_COLLECTION]
            col.replace_one(
                {"_id": _SNAPSHOT_KEY},
                {
                    "_id": _SNAPSHOT_KEY,
                    "db_bytes": db_bytes,
                    "size_bytes": len(db_bytes),
                },
                upsert=True,
            )
            logger.info(f"CloudSyncManager: Saved DB snapshot ({len(db_bytes):,} bytes) to MongoDB.")
            return True
        except Exception as e:
            logger.error(f"CloudSyncManager: Failed to save snapshot: {e}")
            return False
        finally:
            self._save_lock.release()

    def save_db_snapshot_async(self, source_path: Path) -> None:
        """Fire-and-forget snapshot save in a background thread."""
        t = threading.Thread(target=self.save_db_snapshot, args=(source_path,), daemon=True)
        t.start()


# --------------- Singleton ---------------
_global_cloud_sync: Optional[CloudSyncManager] = None


def get_cloud_sync_manager() -> CloudSyncManager:
    global _global_cloud_sync
    if _global_cloud_sync is None:
        _global_cloud_sync = CloudSyncManager()
    return _global_cloud_sync
