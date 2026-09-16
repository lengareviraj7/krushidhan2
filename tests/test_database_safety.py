"""
Automated Pytest Suite for Phase 2: Database Safety, Integrity, Concurrency, and Isolation.
Tests SQLite connection pragmas, WAL mode, foreign keys, atomic transactions, rollbacks,
diagnostic checks, schema versioning, and shop file-level data isolation.
"""
import threading
import sqlite3
import pytest
from src.db.connection import DatabaseManager


@pytest.fixture
def isolated_db(tmp_path):
    """Fixture providing a fresh file-based database instance."""
    db_file = tmp_path / "test_db_safety.db"
    db_mgr = DatabaseManager(db_file)
    db_mgr.initialize_database(include_seed=True)
    return db_mgr


def test_foreign_keys_and_wal_mode_enabled(isolated_db):
    """Verify that foreign keys are ON and WAL journal mode is active."""
    conn = isolated_db.get_connection()
    try:
        cursor = conn.cursor()
        
        # Verify foreign keys pragma
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        assert fk_status == 1, "PRAGMA foreign_keys must be 1 (ON)"

        # Verify WAL journal mode
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = str(cursor.fetchone()[0]).lower()
        assert journal_mode == "wal", f"Journal mode must be WAL, got {journal_mode}"

        # Verify busy timeout
        cursor.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]
        assert busy_timeout == 5000, f"Busy timeout must be 5000ms, got {busy_timeout}"
    finally:
        conn.close()


def test_atomic_transaction_commit(isolated_db):
    """Verify that multi-statement operations commit atomically on success."""
    with isolated_db.transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO categories (category_name, short_name) VALUES (?, ?);",
            ("Organic Bio-Fertilizers", "BIO"),
        )
        cursor.execute(
            "INSERT INTO manufacturers (manufacturer_name, contact_person) VALUES (?, ?);",
            ("Biostadt India", "Regional Manager"),
        )

    # Verify both records exist after transaction commit
    row_cat = isolated_db.fetch_one("SELECT * FROM categories WHERE short_name = 'BIO';")
    row_mfg = isolated_db.fetch_one("SELECT * FROM manufacturers WHERE manufacturer_name = 'Biostadt India';")

    assert row_cat is not None
    assert row_mfg is not None


def test_atomic_transaction_rollback_on_failure(isolated_db):
    """Verify that any exception during a transaction rolls back ALL statements."""
    with pytest.raises(RuntimeError, match="Simulated mid-transaction failure"):
        with isolated_db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (category_name, short_name) VALUES (?, ?);",
                ("Rollback Test Category", "ROLL"),
            )
            # Intentional exception after statement 1
            raise RuntimeError("Simulated mid-transaction failure")

    # Verify statement 1 was completely rolled back
    row = isolated_db.fetch_one("SELECT * FROM categories WHERE short_name = 'ROLL';")
    assert row is None, "Statement 1 must be rolled back on transaction error"


def test_foreign_key_violation_handling(isolated_db):
    """Verify that foreign key constraints block inserting records with invalid parent references."""
    conn = isolated_db.get_connection()
    try:
        cursor = conn.cursor()
        # Attempting to insert a product referencing a non-existent category_id (e.g. 99999)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO products (product_name, category_id, manufacturer_id, unit_id, tax_group_id)
                VALUES ('Orphan Product', 99999, 1, 1, 1);
                """
            )
    finally:
        conn.close()


def test_schema_initialization_and_version_tracking(isolated_db):
    """Verify schema initialization creates version tracking table with version 1."""
    version = isolated_db.get_schema_version()
    assert version >= 1, f"Expected schema version >= 1, got {version}"


def test_pragma_integrity_and_foreign_key_checks(isolated_db):
    """Verify database diagnostic checks PRAGMA integrity_check and PRAGMA foreign_key_check."""
    integrity_results = isolated_db.check_integrity()
    assert integrity_results == ["ok"], f"Database integrity check failed: {integrity_results}"

    fk_violations = isolated_db.check_foreign_keys()
    assert len(fk_violations) == 0, f"Database foreign key violations detected: {fk_violations}"


def test_shop_data_isolation(tmp_path):
    """Verify that Shop A and Shop B using separate database files maintain 100% data isolation."""
    db_file_a = tmp_path / "shop_a.db"
    db_file_b = tmp_path / "shop_b.db"

    shop_a_mgr = DatabaseManager(db_file_a)
    shop_a_mgr.initialize_database(include_seed=True)

    shop_b_mgr = DatabaseManager(db_file_b)
    shop_b_mgr.initialize_database(include_seed=True)

    # Insert unique product in Shop A
    shop_a_mgr.execute_query(
        "INSERT INTO products (product_name, default_sale_rate) VALUES (?, ?);",
        ("Shop A Exclusive Fertilizer", 750.0),
    )

    # Insert unique product in Shop B
    shop_b_mgr.execute_query(
        "INSERT INTO products (product_name, default_sale_rate) VALUES (?, ?);",
        ("Shop B Exclusive Pesticide", 1200.0),
    )

    # Shop A cannot see Shop B's product
    prod_in_a = shop_a_mgr.fetch_one("SELECT * FROM products WHERE product_name = 'Shop B Exclusive Pesticide';")
    assert prod_in_a is None, "Shop A must not see Shop B data"

    # Shop B cannot see Shop A's product
    prod_in_b = shop_b_mgr.fetch_one("SELECT * FROM products WHERE product_name = 'Shop A Exclusive Fertilizer';")
    assert prod_in_b is None, "Shop B must not see Shop A data"


def test_sqlite_wal_concurrency_safety(isolated_db):
    """Verify that concurrent reader threads do not block writer threads under SQLite WAL mode."""
    reader_errors = []
    writer_errors = []

    def reader_task():
        try:
            for _ in range(10):
                conn = isolated_db.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM products;")
                cur.fetchone()
                conn.close()
        except Exception as e:
            reader_errors.append(e)

    def writer_task():
        try:
            for i in range(5):
                isolated_db.execute_query(
                    "INSERT INTO categories (category_name) VALUES (?);",
                    (f"Concurrent Cat {i}",),
                )
        except Exception as e:
            writer_errors.append(e)

    threads = [
        threading.Thread(target=reader_task),
        threading.Thread(target=reader_task),
        threading.Thread(target=writer_task),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(reader_errors) == 0, f"Reader thread errors: {reader_errors}"
    assert len(writer_errors) == 0, f"Writer thread errors: {writer_errors}"
