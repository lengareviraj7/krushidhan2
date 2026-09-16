"""
Automated Pytest Suite for Phase 3: Stock Integrity & Inventory Safety.
Tests phantom stock bug regression, negative stock prevention, FEFO batch selection,
multi-batch allocation, stock ledger traceability, transaction atomicity, and reconciliation.
"""
import pytest
from src.db.connection import DatabaseManager
from src.models.inventory import StockBatch, StockLedgerEntry
from src.models.master_data import Customer, Product, Supplier
from src.models.purchase import Purchase, PurchaseItem
from src.models.sales import Sale, SaleItem
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.master_data_repository import MasterDataRepository
from src.repositories.purchase_repository import PurchaseRepository
from src.repositories.sales_repository import SalesRepository
from src.services.purchase_service import PurchaseService
from src.services.sales_service import SalesService


@pytest.fixture
def stock_db(tmp_path):
    """Fixture providing an isolated file-based database for stock tests."""
    db_file = tmp_path / "test_stock_integrity.db"
    db_mgr = DatabaseManager(db_file)
    db_mgr.initialize_database(include_seed=True)

    master_repo = MasterDataRepository(db_mgr)
    # Seed Customer 1 and Supplier 1
    master_repo.create_customer(Customer(customer_id=1, customer_name="Test Farmer", mobile="9800000000"))
    master_repo.create_supplier(Supplier(supplier_id=1, supplier_name="Test Supplier", mobile="9800000001"))

    # Seed test products
    for i in range(1, 10):
        master_repo.create_product(
            Product(
                product_id=i,
                product_name=f"Test Agri Product {i}",
                category_id=1,
                manufacturer_id=1,
                unit_id=1,
                tax_group_id=2,
                default_purchase_rate=100.0,
                default_sale_rate=150.0,
                default_mrp=150.0,
            )
        )

    return db_mgr


def test_phantom_stock_bug_regression(stock_db):
    """Regression Test 1: Verify that selling a product with 0 stock raises ValueError and DOES NOT create phantom +100 stock."""
    sales_svc = SalesService(stock_db)

    # Product ID 1 with 0 batches in database initially
    # Attempting to process sale for Product ID 1 without purchasing stock MUST fail with ValueError
    sale = Sale(
        invoice_no="INV-TEST-PHANTOM",
        customer_id=1,
        sale_date="2026-09-16",
        total_taxable=500.0,
        total_cgst=12.5,
        total_sgst=12.5,
        total_igst=0.0,
        total_discount=0.0,
        net_amount=525.0,
        paid_amount=525.0,
        payment_mode="CASH",
        items=[
            SaleItem(
                product_id=1,
                qty=2.0,
                sale_rate=262.5,
                mrp=262.5,
                taxable_amount=500.0,
                cgst_rate=2.5,
                sgst_rate=2.5,
                cgst_amount=12.5,
                sgst_amount=12.5,
                total_amount=525.0,
            )
        ],
    )

    with pytest.raises(ValueError, match="साठा उपलब्ध नाही|Insufficient stock"):
        sales_svc.process_sales_invoice(sale)

    # Verify no phantom stock batch was auto-created in database
    batches = stock_db.fetch_all("SELECT * FROM stock_batches WHERE product_id = 1;")
    assert len(batches) == 0, "No phantom stock batch should be created when stock is unavailable"


def test_negative_stock_prevention(stock_db):
    """Test 2: Verify that directly deducting more stock than available in a batch raises ValueError."""
    inv_repo = InventoryRepository(stock_db)

    # Add a batch with 5 units stock
    batch_id = inv_repo.upsert_batch(
        StockBatch(
            product_id=1,
            batch_no="BATCH-LIMITED-5",
            exp_date="2027-12-31",
            purchase_rate=200.0,
            sale_rate=250.0,
            mrp=250.0,
            current_qty=5.0,
        )
    )

    # Deducting 3 units must succeed (leaves 2)
    inv_repo.deduct_batch_stock(batch_id, 3.0)
    batch = inv_repo.get_batch_by_id(batch_id)
    assert batch.current_qty == 2.0

    # Attempting to deduct 5 units from remaining 2 units MUST fail with ValueError
    with pytest.raises(ValueError, match="साठा अपुरा आहे|Insufficient stock"):
        inv_repo.deduct_batch_stock(batch_id, 5.0)

    # Verify quantity remained 2.0 and did not drop below zero
    batch_after = inv_repo.get_batch_by_id(batch_id)
    assert batch_after.current_qty == 2.0


def test_sale_cannot_exceed_available_stock(stock_db):
    """Test 3: Verify that processing a sale invoice exceeding available stock fails and rolls back."""
    purch_svc = PurchaseService(stock_db)
    sales_svc = SalesService(stock_db)
    inv_repo = InventoryRepository(stock_db)

    # 1. Purchase 10 units of Product 1
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-EXCEED-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=2000.0,
            total_cgst=50.0,
            total_sgst=50.0,
            net_amount=2100.0,
            paid_amount=2100.0,
            payment_type="CASH",
            items=[
                PurchaseItem(
                    product_id=1,
                    batch_no="BATCH-EXCEED-10",
                    qty=10.0,
                    purchase_rate=200.0,
                    sale_rate=250.0,
                    mrp=250.0,
                    taxable_amount=2000.0,
                    total_amount=2100.0,
                )
            ],
        )
    )

    assert inv_repo.get_product_total_stock(1) == 10.0

    # 2. Attempting to sell 15 units MUST fail
    invalid_sale = Sale(
        invoice_no="INV-EXCEED-FAIL",
        customer_id=1,
        sale_date="2026-09-16",
        total_taxable=3750.0,
        net_amount=3750.0,
        paid_amount=3750.0,
        items=[
            SaleItem(
                product_id=1,
                batch_no="BATCH-EXCEED-10",
                qty=15.0,
                sale_rate=250.0,
                mrp=250.0,
                taxable_amount=3750.0,
                total_amount=3750.0,
            )
        ],
    )

    with pytest.raises(ValueError, match="साठा अपुरा आहे|Insufficient"):
        sales_svc.process_sales_invoice(invalid_sale)

    # Verify stock remains exactly 10.0
    assert inv_repo.get_product_total_stock(1) == 10.0


def test_fefo_single_batch_selection(stock_db):
    """Test 4: Verify FEFO batch selection prioritizes earliest expiry date."""
    inv_repo = InventoryRepository(stock_db)

    # Create Batch 1: Expires Dec 2026 (10 units)
    inv_repo.upsert_batch(
        StockBatch(
            product_id=2,
            batch_no="BATCH-DEC26",
            exp_date="2026-12-31",
            purchase_rate=100.0,
            sale_rate=150.0,
            mrp=150.0,
            current_qty=10.0,
        )
    )

    # Create Batch 2: Expires June 2026 (5 units - EARLIER EXPIRY)
    inv_repo.upsert_batch(
        StockBatch(
            product_id=2,
            batch_no="BATCH-JUN26",
            exp_date="2026-06-30",
            purchase_rate=100.0,
            sale_rate=150.0,
            mrp=150.0,
            current_qty=5.0,
        )
    )

    # FEFO query must return BATCH-JUN26 first
    batches = inv_repo.get_available_batches_fefo(product_id=2)
    assert len(batches) == 2
    assert batches[0].batch_no == "BATCH-JUN26"
    assert batches[1].batch_no == "BATCH-DEC26"


def test_zero_stock_batch_ignored(stock_db):
    """Test 6: Verify batches with 0 current quantity are excluded from FEFO batch selection."""
    inv_repo = InventoryRepository(stock_db)

    # Zero stock batch
    inv_repo.upsert_batch(
        StockBatch(
            product_id=3,
            batch_no="BATCH-EMPTY-0",
            exp_date="2026-05-01",
            purchase_rate=100.0,
            sale_rate=150.0,
            mrp=150.0,
            current_qty=0.0,
        )
    )

    # Active batch
    inv_repo.upsert_batch(
        StockBatch(
            product_id=3,
            batch_no="BATCH-ACTIVE-10",
            exp_date="2027-05-01",
            purchase_rate=100.0,
            sale_rate=150.0,
            mrp=150.0,
            current_qty=10.0,
        )
    )

    batches = inv_repo.get_available_batches_fefo(product_id=3)
    assert len(batches) == 1
    assert batches[0].batch_no == "BATCH-ACTIVE-10"


def test_purchase_and_sale_stock_movement_ledger(stock_db):
    """Tests 8, 9 & 10: Verify purchase increases stock and sale decreases stock with exact stock_ledger tracking."""
    purch_svc = PurchaseService(stock_db)
    sales_svc = SalesService(stock_db)
    inv_repo = InventoryRepository(stock_db)

    # 1. Inward purchase of 20 units
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-LEDGER-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=2000.0,
            net_amount=2100.0,
            paid_amount=2100.0,
            payment_type="CASH",
            items=[
                PurchaseItem(
                    product_id=4,
                    batch_no="BATCH-LEDGER-20",
                    qty=20.0,
                    purchase_rate=100.0,
                    sale_rate=150.0,
                    mrp=150.0,
                    taxable_amount=2000.0,
                    total_amount=2100.0,
                )
            ],
        )
    )

    assert inv_repo.get_product_total_stock(4) == 20.0

    # 2. Process sale of 5 units
    sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-LEDGER-1",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=750.0,
            net_amount=750.0,
            paid_amount=750.0,
            payment_mode="CASH",
            items=[
                SaleItem(
                    product_id=4,
                    batch_no="BATCH-LEDGER-20",
                    qty=5.0,
                    sale_rate=150.0,
                    mrp=150.0,
                    taxable_amount=750.0,
                    total_amount=750.0,
                )
            ],
        )
    )

    assert inv_repo.get_product_total_stock(4) == 15.0

    # 3. Verify stock_ledger entries
    ledger_entries = stock_db.fetch_all("SELECT * FROM stock_ledger WHERE product_id = 4 ORDER BY ledger_id ASC;")
    assert len(ledger_entries) == 2

    # Inward Ledger Entry
    assert ledger_entries[0]["transaction_type"] == "PURCHASE"
    assert ledger_entries[0]["qty_in"] == 20.0
    assert ledger_entries[0]["balance_qty"] == 20.0

    # Outward Ledger Entry
    assert ledger_entries[1]["transaction_type"] == "SALE"
    assert ledger_entries[1]["qty_out"] == 5.0
    assert ledger_entries[1]["balance_qty"] == 15.0


def test_failed_sale_transaction_rollback(stock_db):
    """Test 11: Verify intentional transaction error inside process_sales_invoice completely rolls back database changes."""
    sales_svc = SalesService(stock_db)
    inv_repo = InventoryRepository(stock_db)

    # Add batch with 10 units
    batch_id = inv_repo.upsert_batch(
        StockBatch(
            product_id=5,
            batch_no="BATCH-ROLLBACK-10",
            purchase_rate=100.0,
            sale_rate=150.0,
            mrp=150.0,
            current_qty=10.0,
        )
    )

    # Create sale with invalid customer ID (violates foreign key if invalid or triggers exception)
    sale = Sale(
        invoice_no="INV-FAIL-ROLLBACK",
        customer_id=999999,  # Non-existent customer ID
        sale_date="2026-09-16",
        total_taxable=750.0,
        net_amount=750.0,
        paid_amount=0.0,
        payment_mode="CREDIT",
        items=[
            SaleItem(
                product_id=5,
                batch_id=batch_id,
                qty=5.0,
                sale_rate=150.0,
                mrp=150.0,
                taxable_amount=750.0,
                total_amount=750.0,
            )
        ],
    )

    with pytest.raises(Exception):
        sales_svc.process_sales_invoice(sale)

    # Verify stock remained untouched (10.0) and invoice was not persisted
    assert inv_repo.get_product_total_stock(5) == 10.0
    sale_row = stock_db.fetch_one("SELECT * FROM sales WHERE invoice_no = 'INV-FAIL-ROLLBACK';")
    assert sale_row is None


def test_stock_reconciliation_consistency(stock_db):
    """Test 13: Verify Stock Reconciliation Formula (Purchases - Sales == Stored Current Stock)."""
    purch_svc = PurchaseService(stock_db)
    sales_svc = SalesService(stock_db)
    inv_repo = InventoryRepository(stock_db)

    # Inward Purchase 1: 50 units
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-RECON-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=5000.0,
            net_amount=5000.0,
            paid_amount=5000.0,
            items=[
                PurchaseItem(
                    product_id=6,
                    batch_no="B6-1",
                    qty=50.0,
                    purchase_rate=100.0,
                    sale_rate=150.0,
                    mrp=150.0,
                    taxable_amount=5000.0,
                    total_amount=5000.0,
                )
            ],
        )
    )

    # Inward Purchase 2: 30 units
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-RECON-2",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=3000.0,
            net_amount=3000.0,
            paid_amount=3000.0,
            items=[
                PurchaseItem(
                    product_id=6,
                    batch_no="B6-2",
                    qty=30.0,
                    purchase_rate=100.0,
                    sale_rate=150.0,
                    mrp=150.0,
                    taxable_amount=3000.0,
                    total_amount=3000.0,
                )
            ],
        )
    )

    # Sale 1: 20 units
    sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-RECON-1",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=3000.0,
            net_amount=3000.0,
            paid_amount=3000.0,
            items=[
                SaleItem(
                    product_id=6,
                    batch_no="B6-1",
                    qty=20.0,
                    sale_rate=150.0,
                    mrp=150.0,
                    taxable_amount=3000.0,
                    total_amount=3000.0,
                )
            ],
        )
    )

    # Sale 2: 15 units
    sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-RECON-2",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=2250.0,
            net_amount=2250.0,
            paid_amount=2250.0,
            items=[
                SaleItem(
                    product_id=6,
                    batch_no="B6-2",
                    qty=15.0,
                    sale_rate=150.0,
                    mrp=150.0,
                    taxable_amount=2250.0,
                    total_amount=2250.0,
                )
            ],
        )
    )

    # Expected stock = (50 + 30) - (20 + 15) = 45 units
    actual_stock = inv_repo.get_product_total_stock(6)
    assert actual_stock == 45.0

    # Calculate net ledger stock movement
    row_in = stock_db.fetch_one("SELECT COALESCE(SUM(qty_in), 0) as total FROM stock_ledger WHERE product_id = 6;")
    row_out = stock_db.fetch_one("SELECT COALESCE(SUM(qty_out), 0) as total FROM stock_ledger WHERE product_id = 6;")

    tot_in = float(row_in["total"])
    tot_out = float(row_out["total"])

    assert (tot_in - tot_out) == actual_stock
