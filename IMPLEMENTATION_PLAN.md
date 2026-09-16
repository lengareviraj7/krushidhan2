# 🛠️ KRUSHIDHAN AGRI-INPUT SHOP ERP — COMMERCIAL READINESS IMPLEMENTATION PLAN

> **Document Status:** PROPOSED (Awaiting User Review)  
> **Target Version:** 2.0-Commercial-Foundation  
> **Architecture Goal:** Transform working offline ERP into a zero-bug, commercial-grade, multi-shop capable, safe desktop foundation.

---

## 📌 Executive Overview & Strategy

This plan outlines the systematic hardening and completion of the Krushidhan Agri-Input Shop ERP codebase across **12 phases**. All changes preserve the existing **SQLite 3 + Python FastAPI + Vanilla JS SPA** stack and retain **100% offline capability**. No database engine migration or cloud dependencies will be introduced, and Tauri 2 integration will remain paused until full foundation stability is verified.

---

## 🎯 Phase Breakdown & Proposed Changes

### Phase 1: Security Hardening
* **Goal:** Eliminate authentication bypasses and enforce strict RBAC.
* **Files Modified:**
  * [`src/services/auth_service.py`](file:///Users/virajlengare/akash/src/services/auth_service.py)
  * [`src/api/auth_middleware.py`](file:///Users/virajlengare/akash/src/api/auth_middleware.py)
  * [`src/api/routes_auth.py`](file:///Users/virajlengare/akash/src/api/routes_auth.py)
* **Changes:**
  1. **Completely remove hardcoded master passwords** (`krushidhan@2026`, `admin123`, `akash@2026`) from `auth_service.py`.
  2. Enforce bcrypt / salted PBKDF2 password verification exclusively against database password hashes.
  3. Enforce Role-Based Access Control (`ADMIN`, `MANAGER`, `OPERATOR`) on protected FastAPI endpoints using dependency injection (`require_admin_user`, `require_roles(["ADMIN", "MANAGER"])`).

---

### Phase 2: Database Safety & Integrity
* **Goal:** Enforce SQLite ACID parameters, transactions, and index optimizations.
* **Files Modified:**
  * [`src/db/connection.py`](file:///Users/virajlengare/akash/src/db/connection.py)
  * [`src/db/schema.sql`](file:///Users/virajlengare/akash/src/db/schema.sql)
* **Changes:**
  1. Verify connection pragmas: `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, `PRAGMA busy_timeout = 5000;`.
  2. Add indexes on foreign keys and frequently queried fields (`product_id`, `batch_id`, `customer_id`, `supplier_id`, `sale_date`, `purchase_date`, `shop_id`).
  3. Ensure all multi-statement operations run inside `@contextmanager transaction()`.

---

### Phase 3: Stock Integrity & Bug Fixes
* **Goal:** Prevent negative stock, fix phantom stock generation, and enforce FEFO.
* **Files Modified:**
  * [`src/repositories/inventory_repository.py`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py)
  * [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py)
  * [`src/services/purchase_service.py`](file:///Users/virajlengare/akash/src/services/purchase_service.py)
* **Changes:**
  1. **Fix Phantom Stock Bug:** Remove `sale_qty + 100` auto-creation logic in `get_or_create_batch_for_sale()`. Raise explicit `ValueError` if no valid batch with stock exists.
  2. **Negative Stock Guard:** Update `deduct_batch_stock()` to check `current_qty >= qty_to_deduct` before execution; raise `ValueError("Insufficient batch stock available")` if violated.
  3. **FEFO Enforcement:** Restrict batch selection to active non-expired batches with positive stock (`current_qty > 0`).
  4. **Stock Ledger Integrity:** Ensure every stock change (purchase, sale, return) logs a traceable `stock_ledger` entry with updated `balance_qty`.

---

### Phase 4: Sale Returns Workflow Implementation
* **Goal:** Build end-to-end customer return workflow.
* **Files Modified:**
  * [`src/repositories/sales_repository.py`](file:///Users/virajlengare/akash/src/repositories/sales_repository.py)
  * [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py)
  * [`src/api/routes_sales.py`](file:///Users/virajlengare/akash/src/api/routes_sales.py)
* **Changes:**
  1. Implement `create_sale_return()` in `SalesRepository`.
  2. In `SalesService.process_sale_return()`:
     - Validate `return_qty <= sold_qty`.
     - Restore returned stock to target batch via `add_batch_stock()`.
     - Log stock movement entry in `stock_ledger` (`transaction_type='SALE_RETURN'`).
     - Post accounting entry: Credit Customer Ledger / Debit Sales Return Account.
     - Adjust customer balance.
  3. Add API route `POST /api/sales/return`.

---

### Phase 5: Purchase Returns Workflow Implementation
* **Goal:** Build end-to-end supplier return workflow.
* **Files Modified:**
  * [`src/repositories/purchase_repository.py`](file:///Users/virajlengare/akash/src/repositories/purchase_repository.py)
  * [`src/services/purchase_service.py`](file:///Users/virajlengare/akash/src/services/purchase_service.py)
  * [`src/api/routes_purchases.py`](file:///Users/virajlengare/akash/src/api/routes_purchases.py)
* **Changes:**
  1. Implement `create_purchase_return()` in `PurchaseRepository`.
  2. In `PurchaseService.process_purchase_return()`:
     - Validate `return_qty <= purchased_qty` and `return_qty <= current_batch_stock`.
     - Deduct returned quantity from batch stock.
     - Log stock ledger entry (`transaction_type='PURCHASE_RETURN'`).
     - Post accounting entry: Debit Supplier Ledger / Credit Purchase Return Account.
     - Recalculate supplier balance.
  3. Add API route `POST /api/purchases/return`.

---

### Phase 6: Double-Entry Accounting Engine Correction
* **Goal:** Resolve same-account debit/credit bug and enforce `TOTAL DEBIT == TOTAL CREDIT`.
* **Files Modified:**
  * [`src/services/accounting_service.py`](file:///Users/virajlengare/akash/src/services/accounting_service.py)
  * [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py)
  * [`src/services/purchase_service.py`](file:///Users/virajlengare/akash/src/services/purchase_service.py)
* **Changes:**
  1. **Customer Receipts:** Debit Cash/Bank Account (`account_id`), Credit Customer Accounts Receivable Ledger (`account_id`). (Fix duplicate account assignment).
  2. **Supplier Payments:** Debit Supplier Accounts Payable Ledger (`account_id`), Credit Cash/Bank Account (`account_id`).
  3. **Expenses:** Debit Expense Category Account (Rent, Labor, Freight), Credit Cash/Bank Account (`account_id`).
  4. Assert `sum(debit_amount) == sum(credit_amount)` for every created voucher.

---

### Phase 7: Backup and Restore Hardening
* **Goal:** Safe, reliable local backup rotation and integrity verification.
* **Files Modified:**
  * [`src/services/backup_service.py`](file:///Users/virajlengare/akash/src/services/backup_service.py)
  * [`src/api/routes_system.py`](file:///Users/virajlengare/akash/src/api/routes_system.py)
* **Changes:**
  1. Implement automated daily backup on startup if today's backup does not exist.
  2. Implement backup rotation policy (retain latest 30 backups, prune older).
  3. Verify backup file via `PRAGMA quick_check;` before restore.
  4. Require creation of a pre-restore safety snapshot before overwriting `agri_erp.db`.

---

### Phase 8: Multi-Shop Data Isolation Scoping
* **Goal:** Guarantee multi-tenant / multi-shop data isolation in all queries.
* **Files Modified:**
  * [`src/repositories/sales_repository.py`](file:///Users/virajlengare/akash/src/repositories/sales_repository.py)
  * [`src/repositories/purchase_repository.py`](file:///Users/virajlengare/akash/src/repositories/purchase_repository.py)
  * [`src/repositories/inventory_repository.py`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py)
  * [`src/repositories/master_data_repository.py`](file:///Users/virajlengare/akash/src/repositories/master_data_repository.py)
  * [`src/repositories/accounting_repository.py`](file:///Users/virajlengare/akash/src/repositories/accounting_repository.py)
* **Changes:**
  1. Audit every query in repository classes and ensure `shop_id` filter is present where applicable (`WHERE shop_id = ?`).

---

### Phase 9: GST & Billing Regression Verification
* **Goal:** Preserve working GST, invoicing, and Devanagari PDF generation.
* **Files Modified:**
  * [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py)
  * [`src/printing/invoice_pdf.py`](file:///Users/virajlengare/akash/src/printing/invoice_pdf.py)
* **Changes:**
  1. Run automated checks on CGST, SGST, IGST calculations, tax-inclusive pricing, HSN summaries, and PDF generation with Marathi fonts.

---

### Phase 10: Automated Testing Suite
* **Goal:** Build robust pytest test suite for business logic.
* **New Test Files Created:**
  * `tests/test_auth_security.py`
  * `tests/test_stock_fefo.py`
  * `tests/test_accounting_engine.py`
  * `tests/test_returns_workflow.py`
  * `tests/test_backup_restore.py`
  * `tests/test_shop_isolation.py`
* **Changes:**
  1. Use temporary in-memory or isolated file-based SQLite databases for test execution.
  2. Verify 100% pass rate on all business logic tests.

---

### Phase 11: Safe Logging & Error Handling
* **Goal:** Centralized logging without sensitive data leaks.
* **Files Modified:**
  * [`src/utils/logger.py`](file:///Users/virajlengare/akash/src/utils/logger.py)
  * [`src/app.py`](file:///Users/virajlengare/akash/src/app.py)
* **Changes:**
  1. Setup safe file-based rotating logger (`logs/agri_erp.log`).
  2. Filter out passwords and tokens from log statements.

---

### Phase 12: Commercial Audit & Readiness Documentation
* **Goal:** Final audit and report generation.
* **Files Created:**
  * `COMMERCIAL_READINESS_REPORT.md`
  * `SECURITY_AUDIT_REPORT.md`
  * `STOCK_ACCOUNTING_AUDIT.md`
  * `TEST_REPORT.md`
  * `MIGRATION_NOTES.md`

---

## 🧪 Verification & Testing Strategy

1. **Automated Unit & Integration Tests:** Run `pytest tests/` after each phase.
2. **Database Integrity Checks:** Execute `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;`.
3. **Accounting Balance Checks:** Run `SELECT SUM(debit_amount) - SUM(credit_amount) FROM journal_items;` (Must equal 0.00).
4. **Stock Ledger Consistency:** Compare `SUM(current_qty)` in `stock_batches` against net ledger totals in `stock_ledger`.

---

## ⚠️ Potential Risks & Mitigations

* **Risk 1:** Disabling phantom batch auto-creation might break existing frontend if user tries to sell an item with 0 stock.
  * *Mitigation:* Frontend will receive a clear 400 Bad Request message: *"पर्याप्त साठा उपलब्ध नाही (Insufficient stock available)"*.
* **Risk 2:** Fixing accounting vouchers might expose past invalid voucher entries in `journal_items`.
  * *Mitigation:* Accounting fixes will apply to all newly generated transactions without corrupting existing database rows.
