"""
Test Suite for Database Schema and Initializer (Phase 1).
"""
import sqlite3
import pytest
from src.db.connection import DatabaseManager

EXPECTED_TABLES = [
    # 1. Master Data
    "categories",
    "manufacturers",
    "units",
    "unit_conversions",
    "tax_groups",
    "crops",
    "products",
    "customer_groups",
    "customers",
    "suppliers",
    "extra_charges_master",
    # 2. Inventory
    "stock_batches",
    "stock_ledger",
    # 3. Purchase
    "purchases",
    "purchase_items",
    "purchase_returns",
    "purchase_return_items",
    # 4. Sales
    "sales",
    "sale_items",
    "sales_returns",
    "sales_return_items",
    # 5. Accounts
    "ledger_accounts",
    "vouchers",
    "ledger_entries",
    "expense_categories",
    "expenses",
    # 6. System
    "users",
    "company_settings",
    "audit_log",
    "backup_log",
]


@pytest.fixture
def db_manager(tmp_path):
    """Provides a fresh SQLite database instance for each test."""
    db_file = tmp_path / "test_agri_erp.db"
    manager = DatabaseManager(db_path=db_file)
    manager.initialize_database(include_seed=True)
    return manager


def test_all_26_tables_exist(db_manager):
    """Verify that all 26 tables in the schema specification are created."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()

    for expected_table in EXPECTED_TABLES:
        assert expected_table in tables, f"Expected table '{expected_table}' was not found in schema!"
    
    assert len(tables) >= 26, f"Expected at least 26 tables, but found {len(tables)}"


def test_seed_data_loaded_correctly(db_manager):
    """Verify that initial master seeds (Tax slabs, Units, Chart of accounts, Admin user) are populated."""
    # 1. Check Units
    units = db_manager.fetch_all("SELECT * FROM units;")
    assert len(units) >= 9
    unit_symbols = [u["symbol"] for u in units]
    assert "KG" in unit_symbols
    assert "BAG" in unit_symbols
    assert "LTR" in unit_symbols

    # 2. Check Tax Groups
    tax_groups = db_manager.fetch_all("SELECT * FROM tax_groups;")
    assert len(tax_groups) >= 5
    tax_names = [tg["tax_group_name"] for tg in tax_groups]
    assert any("5%" in name for name in tax_names)
    assert any("18%" in name for name in tax_names)

    # 3. Check Chart of Accounts
    accounts = db_manager.fetch_all("SELECT * FROM ledger_accounts;")
    assert len(accounts) >= 15
    account_names = [a["account_name"] for a in accounts]
    assert "Cash in Hand" in account_names
    assert "Sales Account" in account_names
    assert "Purchase Account" in account_names
    assert "CGST Output Account" in account_names

    # 4. Check Default Admin User
    admin = db_manager.fetch_one("SELECT * FROM users WHERE username = 'admin';")
    assert admin is not None
    assert admin["role"] == "ADMIN"
    assert admin["is_active"] == 1

    # 5. Check Company Profile
    profile = db_manager.fetch_one("SELECT * FROM company_settings WHERE setting_id = 1;")
    assert profile is not None
    assert "कृषीधन" in profile["company_name"] or "Krishi" in profile["company_name"]


def test_foreign_key_constraints_enforced(db_manager):
    """Verify that foreign key constraints raise an IntegrityError when invalid references are inserted."""
    # Attempt to insert a product with non-existent category_id and manufacturer_id
    with pytest.raises(sqlite3.IntegrityError):
        db_manager.execute_query(
            """
            INSERT INTO products (product_name, category_id, manufacturer_id, unit_id, tax_group_id)
            VALUES ('Invalid Product', 99999, 99999, 99999, 99999);
            """
        )


def test_transaction_rollback_on_failure(db_manager):
    """Verify that transactions rollback atomically if an error occurs mid-transaction."""
    try:
        with db_manager.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category_name, short_name) VALUES ('Test Cat 1', 'TC1');")
            # Force an error
            cursor.execute("INSERT INTO non_existent_table (xyz) VALUES (123);")
    except Exception:
        pass

    # Verify 'Test Cat 1' was rolled back and does not exist
    record = db_manager.fetch_one("SELECT * FROM categories WHERE category_name = 'Test Cat 1';")
    assert record is None, "Transaction should have rolled back but record was persisted!"


def test_performance_indexes_created(db_manager):
    """Verify that performance indexes exist."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = [row["name"] for row in cursor.fetchall()]
    conn.close()

    assert "idx_products_category" in indexes
    assert "idx_stock_batches_exp" in indexes
    assert "idx_sales_date" in indexes
    assert "idx_purchases_date" in indexes


def test_create_manufacturer_and_unit(db_manager):
    """Verify creating dynamic manufacturer and unit in MasterDataRepository."""
    from src.repositories.master_data_repository import MasterDataRepository
    from src.models.master_data import Unit, Manufacturer

    repo = MasterDataRepository(db_manager)

    # 1. Create Manufacturer
    mfg_id = repo.get_or_create_manufacturer("Tata Rallis")
    assert mfg_id > 0
    # Retrieve again (idempotent)
    mfg_id_2 = repo.get_or_create_manufacturer("Tata Rallis")
    assert mfg_id == mfg_id_2

    # 2. Create Unit
    unit_id = repo.create_unit(Unit(unit_name="Bottle", symbol="BTL"))
    assert unit_id > 0
    # Retrieve again (idempotent)
    unit_id_2 = repo.create_unit(Unit(unit_name="Bottle", symbol="BTL"))
    assert unit_id == unit_id_2


def test_delete_product(db_manager):
    """Verify deleting/deactivating product in MasterDataRepository."""
    from src.repositories.master_data_repository import MasterDataRepository
    from src.models.master_data import Product, Category

    repo = MasterDataRepository(db_manager)
    cat_id = repo.create_category(Category(category_name="Test Deletion Cat"))

    prod_id = repo.create_product(Product(
        product_name="Product To Delete",
        category_id=cat_id,
        default_sale_rate=100.0
    ))
    assert prod_id > 0

    success = repo.delete_product(prod_id)
    assert success is True

    prods_after = repo.search_products("Product To Delete")
    assert len(prods_after) == 0
