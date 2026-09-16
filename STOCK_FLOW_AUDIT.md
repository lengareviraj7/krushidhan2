# 📦 STOCK LIFECYCLE & INVENTORY AUDIT REPORT (PHASE 3)

> **Date:** 16 September 2026  
> **Auditor:** Senior Software & Production ERP Architect  
> **Status:** AUDITED — READY FOR FIXES

---

## 📌 1. Complete Stock Flow Mapping

### A. Purchase Inward Flow
```
[Purchase Invoice Input]
       │
       ▼
PurchaseService.process_inward_purchase()
       │
       ├─► PurchaseRepository.create_purchase() ──────────► INSERT INTO purchases & purchase_items
       │
       ├─► InventoryRepository.upsert_batch() ────────────► INSERT / UPDATE stock_batches 
       │                                                    (current_qty += (qty + free_qty))
       │
       ├─► InventoryRepository.record_stock_movement() ──► INSERT INTO stock_ledger
       │                                                    (transaction_type='PURCHASE', qty_in > 0)
       │
       ├─► MasterDataRepository.update_supplier_balance() ► UPDATE suppliers (current_balance += unpaid_due)
       │
       └─► AccountingService / Voucher ───────────────────► INSERT INTO vouchers & ledger_entries
```

* **Files Involved:**
  * [`src/services/purchase_service.py`](file:///Users/virajlengare/akash/src/services/purchase_service.py) (`process_inward_purchase`)
  * [`src/repositories/purchase_repository.py`](file:///Users/virajlengare/akash/src/repositories/purchase_repository.py) (`create_purchase`)
  * [`src/repositories/inventory_repository.py`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py) (`upsert_batch`, `record_stock_movement`)
* **Tables Updated:** `purchases`, `purchase_items`, `stock_batches`, `stock_ledger`, `suppliers`, `vouchers`, `ledger_entries`.

---

### B. Sale & Stock Deduction Flow
```
[POS Billing Invoice Input]
       │
       ▼
SalesService.process_sales_invoice()
       │
       ├─► InventoryRepository.get_or_create_batch_for_sale() ──► Resolves active FEFO batch
       │                                                          [⚠️ BUG: Creates phantom +100 batch if none found]
       │
       ├─► InventoryRepository.deduct_batch_stock() ────────────► UPDATE stock_batches
       │                                                          (current_qty -= qty)
       │                                                          [⚠️ BUG: Allows negative stock if current_qty < qty]
       │
       ├─► SalesRepository.create_sale() ────────────────────────► INSERT INTO sales & sale_items
       │
       ├─► InventoryRepository.record_stock_movement() ──────────► INSERT INTO stock_ledger
       │                                                          (transaction_type='SALE', qty_out > 0)
       │
       ├─► MasterDataRepository.update_customer_balance() ───────► UPDATE customers (current_balance += unpaid_due)
       │
       └─► AccountingService / Voucher ──────────────────────────► INSERT INTO vouchers & ledger_entries
```

* **Files Involved:**
  * [`src/services/sales_service.py`](file:///Users/virajlengare/akash/src/services/sales_service.py) (`process_sales_invoice`)
  * [`src/repositories/sales_repository.py`](file:///Users/virajlengare/akash/src/repositories/sales_repository.py) (`create_sale`)
  * [`src/repositories/inventory_repository.py`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py) (`get_or_create_batch_for_sale`, `deduct_batch_stock`, `record_stock_movement`)
* **Tables Updated:** `sales`, `sale_items`, `stock_batches`, `stock_ledger`, `customers`, `vouchers`, `ledger_entries`.

---

## 🚨 2. Known Stock Inconsistencies & Root Cause Analysis

### Issue 1: Phantom +100 Stock Bug
* **Location:** [`src/repositories/inventory_repository.py:143-152`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py#L143-L152)
* **Root Cause:** In `get_or_create_batch_for_sale()`, if no batch exists or no batch has positive stock, it automatically executes an `INSERT INTO stock_batches` with `current_qty = sale_qty + 100`!
* **Impact:** Manufactured fake stock, polluting inventory data and stock valuation.
* **Fix Plan:** Remove auto-creation of phantom stock. If no valid batch with sufficient stock exists, raise an explicit `ValueError("पर्याप्त साठा उपलब्ध नाही (Insufficient stock available for product)")`.

---

### Issue 2: Unchecked Negative Stock
* **Location:** [`src/repositories/inventory_repository.py:180-192`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py#L180-L192)
* **Root Cause:** `deduct_batch_stock()` executes `UPDATE stock_batches SET current_qty = current_qty - ? WHERE batch_id = ?;` without checking if `current_qty >= qty_to_deduct`.
* **Impact:** Stock batch quantities could drop below zero.
* **Fix Plan:** Add pre-deduction check: verify `current_qty >= qty_to_deduct`. If violated, raise `ValueError("Insufficient stock in target batch")`. Because all operations run inside `@contextmanager transaction()`, raising this exception triggers a 100% atomic rollback of the invoice creation!

---

### Issue 3: FEFO Allocation & Multi-Batch Support
* **Location:** [`src/repositories/inventory_repository.py:125-133`](file:///Users/virajlengare/akash/src/repositories/inventory_repository.py#L125-L133)
* **Root Cause:** `get_available_batches_fefo()` fetches batches sorted by `exp_date ASC`, but single-batch resolution did not handle multi-batch splits when a requested quantity spans multiple small batches.
* **Fix Plan:** Implement multi-batch FEFO resolution helper so billing can draw from the earliest expiring batch first and automatically split across secondary batches if needed.

---

## 🏛️ 3. Authoritative Single Source of Truth

* **Batch Stock:** `stock_batches.current_qty` (Authoritative quantity for each product batch).
* **Product Stock:** `SUM(stock_batches.current_qty)` for a given `product_id`.
* **Stock Movement Audit:** Immutable `stock_ledger` records (`qty_in`, `qty_out`, `balance_qty`).
