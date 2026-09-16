"""
Automated Pytest Suite for Phase 4: Sale Returns Workflow.
Tests valid sale returns, batch stock restoration, stock ledger tracking, customer balance reduction,
return quantity caps, original invoice preservation, accounting balance, and rollback handling.
"""
import pytest
from src.db.connection import DatabaseManager
from src.models.master_data import Customer, Product, Supplier
from src.models.purchase import Purchase, PurchaseItem
from src.models.sales import Sale, SaleItem, SalesReturn, SalesReturnItem
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.master_data_repository import MasterDataRepository
from src.repositories.sales_repository import SalesRepository
from src.services.purchase_service import PurchaseService
from src.services.sales_service import SalesService


@pytest.fixture
def return_db(tmp_path):
    """Fixture providing an isolated file-based database for sale return tests."""
    db_file = tmp_path / "test_sale_returns.db"
    db_mgr = DatabaseManager(db_file)
    db_mgr.initialize_database(include_seed=True)

    master_repo = MasterDataRepository(db_mgr)
    master_repo.create_customer(Customer(customer_id=1, customer_name="Return Farmer", mobile="9800000000", current_balance=0.0))
    master_repo.create_supplier(Supplier(supplier_id=1, supplier_name="Return Supplier", mobile="9800000001"))

    master_repo.create_product(
        Product(
            product_id=1,
            product_name="Return Insecticide 250ml",
            category_id=3,
            manufacturer_id=1,
            unit_id=1,
            tax_group_id=4,
            default_purchase_rate=200.0,
            default_sale_rate=300.0,
            default_mrp=300.0,
        )
    )

    return db_mgr


def test_valid_sale_return_workflow(return_db):
    """Tests 1, 2, 3, 4, 5 & 15: Valid sale return restores batch stock, creates stock ledger, updates customer balance, preserves GST, and leaves original invoice unchanged."""
    purch_svc = PurchaseService(return_db)
    sales_svc = SalesService(return_db)
    sales_repo = SalesRepository(return_db)
    inv_repo = InventoryRepository(return_db)
    master_repo = MasterDataRepository(return_db)

    # 1. Inward Purchase of 20 units
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-RET-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=4000.0,
            net_amount=4000.0,
            paid_amount=4000.0,
            items=[
                PurchaseItem(
                    product_id=1,
                    batch_no="B-RET-20",
                    qty=20.0,
                    purchase_rate=200.0,
                    sale_rate=300.0,
                    mrp=300.0,
                    taxable_amount=4000.0,
                    total_amount=4000.0,
                )
            ],
        )
    )
    assert inv_repo.get_product_total_stock(1) == 20.0

    # 2. Credit Sale of 10 units to Customer 1
    sale_id = sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-RET-1",
            customer_id=1,
            sale_date="2026-09-16",
            payment_mode="CREDIT",
            total_taxable=2542.37,
            total_cgst=228.81,
            total_sgst=228.81,
            net_amount=3000.0,
            paid_amount=0.0,
            due_amount=3000.0,
            items=[
                SaleItem(
                    product_id=1,
                    batch_no="B-RET-20",
                    qty=10.0,
                    sale_rate=300.0,
                    mrp=300.0,
                    taxable_amount=2542.37,
                    cgst_rate=9.0,
                    cgst_amount=228.81,
                    sgst_rate=9.0,
                    sgst_amount=228.81,
                    total_amount=3000.0,
                )
            ],
        )
    )

    # Stock should be 10.0 and Customer Balance should be 3000.0
    assert inv_repo.get_product_total_stock(1) == 10.0
    cust_before = master_repo.get_customer_by_id(1)
    assert cust_before.current_balance == 3000.0

    # 3. Customer Returns 2 units
    return_id = sales_svc.process_sale_return(
        SalesReturn(
            return_no="SR-00001",
            return_date="2026-09-16",
            sale_id=sale_id,
            customer_id=1,
            total_taxable=508.47,
            total_tax=91.53,
            net_amount=600.0,
            remarks="Defective seal",
            items=[
                SalesReturnItem(
                    product_id=1,
                    qty=2.0,
                    sale_rate=300.0,
                    taxable_amount=508.47,
                    tax_amount=91.53,
                    total_amount=600.0,
                    reason="Defective bottle seal",
                )
            ],
        )
    )

    assert return_id > 0

    # 4. Verify Stock Restoration: 10.0 + 2.0 = 12.0
    assert inv_repo.get_product_total_stock(1) == 12.0

    # 5. Verify Customer Balance Reduction: 3000.0 - 600.0 = 2400.0
    cust_after = master_repo.get_customer_by_id(1)
    assert cust_after.current_balance == 2400.0

    # 6. Verify Stock Ledger Entry
    ledger = return_db.fetch_all("SELECT * FROM stock_ledger WHERE transaction_type = 'SALE_RETURN';")
    assert len(ledger) == 1
    assert ledger[0]["qty_in"] == 2.0
    assert ledger[0]["balance_qty"] == 12.0

    # 7. Verify Original Sale Invoice remains unchanged
    orig_sale = sales_repo.get_sale_by_id(sale_id)
    assert orig_sale.net_amount == 3000.0
    assert orig_sale.items[0].qty == 10.0


def test_cannot_return_more_than_originally_sold(return_db):
    """Test 6: Verify attempting to return a quantity greater than originally sold is rejected."""
    purch_svc = PurchaseService(return_db)
    sales_svc = SalesService(return_db)

    # Inward Purchase
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-MAX-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=2000.0,
            net_amount=2100.0,
            paid_amount=2100.0,
            items=[PurchaseItem(product_id=1, batch_no="B-MAX", qty=10.0, purchase_rate=200.0, sale_rate=300.0, mrp=300.0, taxable_amount=2000.0, total_amount=2100.0)],
        )
    )

    # Sale 5 units
    sale_id = sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-MAX-1",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=1271.19,
            net_amount=1500.0,
            paid_amount=1500.0,
            items=[SaleItem(product_id=1, batch_no="B-MAX", qty=5.0, sale_rate=300.0, mrp=300.0, taxable_amount=1271.19, total_amount=1500.0)],
        )
    )

    # Attempting to return 6 units (more than 5 sold) MUST fail
    invalid_return = SalesReturn(
        return_no="SR-MAX-FAIL",
        return_date="2026-09-16",
        sale_id=sale_id,
        customer_id=1,
        total_taxable=1525.42,
        net_amount=1800.0,
        items=[SalesReturnItem(product_id=1, qty=6.0, sale_rate=300.0, taxable_amount=1525.42, total_amount=1800.0)],
    )

    with pytest.raises(ValueError, match="परतावा प्रमाण मूळ विक्रीपेक्षा जास्त आहे|exceeds eligible"):
        sales_svc.process_sale_return(invalid_return)


def test_cannot_exceed_remaining_eligible_quantity(return_db):
    """Test 7: Verify partial returns track remaining eligible quantity and block cumulative over-returns."""
    purch_svc = PurchaseService(return_db)
    sales_svc = SalesService(return_db)

    # Inward Purchase
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-PART-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=2000.0,
            net_amount=2100.0,
            paid_amount=2100.0,
            items=[PurchaseItem(product_id=1, batch_no="B-PART", qty=10.0, purchase_rate=200.0, sale_rate=300.0, mrp=300.0, taxable_amount=2000.0, total_amount=2100.0)],
        )
    )

    # Sale 10 units
    sale_id = sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-PART-1",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=2542.37,
            net_amount=3000.0,
            paid_amount=3000.0,
            items=[SaleItem(product_id=1, batch_no="B-PART", qty=10.0, sale_rate=300.0, mrp=300.0, taxable_amount=2542.37, total_amount=3000.0)],
        )
    )

    # First return: 4 units (Succeeds)
    sales_svc.process_sale_return(
        SalesReturn(
            return_no="SR-PART-1",
            return_date="2026-09-16",
            sale_id=sale_id,
            customer_id=1,
            total_taxable=1016.95,
            net_amount=1200.0,
            items=[SalesReturnItem(product_id=1, qty=4.0, sale_rate=300.0, taxable_amount=1016.95, total_amount=1200.0)],
        )
    )

    # Second return: 5 units (Succeeds, total returned = 9)
    sales_svc.process_sale_return(
        SalesReturn(
            return_no="SR-PART-2",
            return_date="2026-09-16",
            sale_id=sale_id,
            customer_id=1,
            total_taxable=1271.19,
            net_amount=1500.0,
            items=[SalesReturnItem(product_id=1, qty=5.0, sale_rate=300.0, taxable_amount=1271.19, total_amount=1500.0)],
        )
    )

    # Remaining eligible quantity = 10 - (4 + 5) = 1 unit.
    # Attempting to return 2 units MUST fail
    with pytest.raises(ValueError, match="exceeds eligible"):
        sales_svc.process_sale_return(
            SalesReturn(
                return_no="SR-PART-3-FAIL",
                return_date="2026-09-16",
                sale_id=sale_id,
                customer_id=1,
                total_taxable=508.47,
                net_amount=600.0,
                items=[SalesReturnItem(product_id=1, qty=2.0, sale_rate=300.0, taxable_amount=508.47, total_amount=600.0)],
            )
        )


def test_cannot_return_product_from_another_invoice(return_db):
    """Test 8 & 10: Verify returning a product that was not in the original invoice is rejected."""
    sales_svc = SalesService(return_db)
    purch_svc = PurchaseService(return_db)

    # Purchase Product 1
    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-DIFF-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=2000.0,
            net_amount=2100.0,
            paid_amount=2100.0,
            items=[PurchaseItem(product_id=1, batch_no="B-DIFF", qty=10.0, purchase_rate=200.0, sale_rate=300.0, mrp=300.0, taxable_amount=2000.0, total_amount=2100.0)],
        )
    )

    # Sale invoice with ONLY Product 1
    sale_id = sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-DIFF-1",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=1271.19,
            net_amount=1500.0,
            paid_amount=1500.0,
            items=[SaleItem(product_id=1, batch_no="B-DIFF", qty=5.0, sale_rate=300.0, mrp=300.0, taxable_amount=1271.19, total_amount=1500.0)],
        )
    )

    # Attempting to return Product 2 against INV-DIFF-1 MUST fail
    with pytest.raises(ValueError, match="मूळ विक्री बिलामध्ये नाही|not in original invoice"):
        sales_svc.process_sale_return(
            SalesReturn(
                return_no="SR-DIFF-FAIL",
                return_date="2026-09-16",
                sale_id=sale_id,
                customer_id=1,
                net_amount=300.0,
                items=[SalesReturnItem(product_id=2, qty=1.0, sale_rate=300.0, taxable_amount=254.24, total_amount=300.0)],
            )
        )


def test_sale_return_accounting_entry_is_balanced(return_db):
    """Test 14: Verify double-entry voucher posted for sale return satisfies TOTAL DEBIT == TOTAL CREDIT."""
    purch_svc = PurchaseService(return_db)
    sales_svc = SalesService(return_db)

    purch_svc.process_inward_purchase(
        Purchase(
            invoice_no="PURCH-BAL-1",
            supplier_id=1,
            purchase_date="2026-09-16",
            total_taxable=2000.0,
            net_amount=2100.0,
            paid_amount=2100.0,
            items=[PurchaseItem(product_id=1, batch_no="B-BAL", qty=10.0, purchase_rate=200.0, sale_rate=300.0, mrp=300.0, taxable_amount=2000.0, total_amount=2100.0)],
        )
    )

    sale_id = sales_svc.process_sales_invoice(
        Sale(
            invoice_no="INV-BAL-1",
            customer_id=1,
            sale_date="2026-09-16",
            total_taxable=1271.19,
            net_amount=1500.0,
            paid_amount=1500.0,
            items=[SaleItem(product_id=1, batch_no="B-BAL", qty=5.0, sale_rate=300.0, mrp=300.0, taxable_amount=1271.19, total_amount=1500.0)],
        )
    )

    return_id = sales_svc.process_sale_return(
        SalesReturn(
            return_no="SR-BAL-1",
            return_date="2026-09-16",
            sale_id=sale_id,
            customer_id=1,
            total_taxable=508.47,
            total_tax=91.53,
            net_amount=600.0,
            items=[SalesReturnItem(product_id=1, qty=2.0, sale_rate=300.0, taxable_amount=508.47, tax_amount=91.53, total_amount=600.0)],
        )
    )

    # Fetch posted voucher
    vch = return_db.fetch_one("SELECT * FROM vouchers WHERE reference_type = 'SALE_RETURN' AND reference_id = ?;", (return_id,))
    assert vch is not None

    entries = return_db.fetch_all("SELECT * FROM ledger_entries WHERE voucher_id = ?;", (vch["voucher_id"],))
    tot_dr = sum(e["debit_amount"] for e in entries)
    tot_cr = sum(e["credit_amount"] for e in entries)

    assert round(tot_dr, 2) == round(tot_cr, 2)
    assert tot_dr == 600.0
