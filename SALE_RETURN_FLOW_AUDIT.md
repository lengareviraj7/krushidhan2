# 🔄 SALE RETURN WORKFLOW AUDIT REPORT (PHASE 4)

> **Date:** 16 September 2026  
> **Auditor:** Senior Software & Production ERP Architect  
> **Status:** AUDITED — READY FOR IMPLEMENTATION

---

## 📌 1. Existing Database Schema Audit

The database schema already defines two dedicated tables for customer sales returns:

### 1. `sales_returns` (Header Table)
* `return_id INTEGER PRIMARY KEY AUTOINCREMENT`
* `return_no TEXT NOT NULL UNIQUE` (e.g., `SR-2627-0001`)
* `return_date TEXT NOT NULL`
* `sale_id INTEGER REFERENCES sales(sale_id)`
* `customer_id INTEGER NOT NULL REFERENCES customers(customer_id)`
* `total_taxable REAL DEFAULT 0`
* `total_tax REAL DEFAULT 0`
* `round_off REAL DEFAULT 0`
* `net_amount REAL NOT NULL`
* `remarks TEXT`
* `created_at TEXT DEFAULT CURRENT_TIMESTAMP`

### 2. `sales_return_items` (Line Items Table)
* `return_item_id INTEGER PRIMARY KEY AUTOINCREMENT`
* `return_id INTEGER NOT NULL REFERENCES sales_returns(return_id) ON DELETE CASCADE`
* `product_id INTEGER NOT NULL REFERENCES products(product_id)`
* `batch_id INTEGER REFERENCES stock_batches(batch_id)`
* `qty REAL NOT NULL`
* `sale_rate REAL NOT NULL`
* `taxable_amount REAL NOT NULL`
* `tax_amount REAL DEFAULT 0`
* `total_amount REAL NOT NULL`
* `reason TEXT`

---

## 🔍 2. Existing Codebase Audit (What Exists vs What is Missing)

* **Models:** [`src/models/sales.py`](file:///Users/virajlengare/akash/src/models/sales.py) contains Pydantic models `SalesReturn` and `SalesReturnItem`.
* **Repository Layer:** [`src/repositories/sales_repository.py`](file:///Users/virajlengare/akash/src/repositories/sales_repository.py) needs `create_sale_return()` and `get_already_returned_qty()`.
* **Service Layer:** [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py) needs `process_sale_return()` business logic with:
  1. Original invoice validation
  2. Server-side return quantity validation (`qty <= sold_qty - already_returned_qty`)
  3. Stock restoration (`add_batch_stock`)
  4. Stock ledger entry creation (`transaction_type = 'SALE_RETURN'`)
  5. Customer balance adjustment (`current_balance -= net_amount` for credit sales)
  6. Double-entry accounting voucher (`DEBIT Sales Return Account`, `CREDIT Accounts Receivable / Cash`)
* **API Layer:** [`src/api/routes_sales.py`](file:///Users/virajlengare/akash/src/api/routes_sales.py) needs `POST /api/sales/return` endpoint and `GET /api/sales/{sale_id}/eligible-returns`.
* **Frontend UI:** [`src/web/static/js/app.js`](file:///Users/virajlengare/akash/src/web/static/js/app.js) & [`src/web/templates/index.html`](file:///Users/virajlengare/akash/src/web/templates/index.html) need a "विक्री परतावा (Sale Return)" modal allowing cashier to pick an invoice, select line items, specify return quantities, and submit.

---

## 🛠️ 3. Exact Files to Modify

1. [`src/repositories/sales_repository.py`](file:///Users/virajlengare/akash/src/repositories/sales_repository.py): Add `create_sale_return()`, `get_already_returned_qty_for_sale()`, `generate_next_return_no()`.
2. [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py): Add `process_sale_return()` and `get_eligible_return_items()`.
3. [`src/api/routes_sales.py`](file:///Users/virajlengare/akash/src/api/routes_sales.py): Add return endpoints `POST /api/sales/return` and `GET /api/sales/{sale_id}/eligible-returns`.
4. [`src/web/templates/index.html`](file:///Users/virajlengare/akash/src/web/templates/index.html): Add Sale Return modal form.
5. [`src/web/static/js/app.js`](file:///Users/virajlengare/akash/src/web/static/js/app.js): Add Sale Return frontend handler `openSaleReturnModal()`, `submitSaleReturn()`.
6. [`tests/test_sale_returns.py`](file:///Users/virajlengare/akash/tests/test_sale_returns.py): New automated test suite.
