"""
Data Access Layer (Repository) for Batch Inventory and Stock Movement Ledger.
"""
from __future__ import annotations

from datetime import datetime
import sqlite3
from typing import Any, Dict, List, Optional
from src.models.inventory import StockBatch, StockLedgerEntry
from src.repositories.base_repository import BaseRepository


class InventoryRepository(BaseRepository):
    """Repository for managing batch-wise inventory and stock ledger audit trails."""

    def upsert_batch(self, batch: StockBatch, conn: Optional[sqlite3.Connection] = None) -> int:
        """Create or update a stock batch (matched by product_id and batch_no)."""
        sql_check = "SELECT batch_id, current_qty FROM stock_batches WHERE product_id = ? AND batch_no = ?;"
        
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            cursor.execute(sql_check, (batch.product_id, batch.batch_no))
            existing = cursor.fetchone()

            if existing:
                batch_id = existing["batch_id"]
                sql_update = """
                    UPDATE stock_batches SET
                        mfg_date = COALESCE(?, mfg_date),
                        exp_date = COALESCE(?, exp_date),
                        purchase_rate = ?,
                        sale_rate = ?,
                        mrp = ?,
                        current_qty = current_qty + ?
                    WHERE batch_id = ?;
                """
                cursor.execute(
                    sql_update,
                    (
                        batch.mfg_date,
                        batch.exp_date,
                        batch.purchase_rate,
                        batch.sale_rate,
                        batch.mrp,
                        batch.current_qty,
                        batch_id,
                    ),
                )
                if conn is None:
                    executor.commit()
                return batch_id
            else:
                sql_insert = """
                    INSERT INTO stock_batches (
                        product_id, batch_no, mfg_date, exp_date,
                        purchase_rate, sale_rate, mrp, opening_qty, current_qty, barcode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(
                    sql_insert,
                    (
                        batch.product_id,
                        batch.batch_no,
                        batch.mfg_date,
                        batch.exp_date,
                        batch.purchase_rate,
                        batch.sale_rate,
                        batch.mrp,
                        batch.opening_qty,
                        batch.current_qty,
                        batch.barcode,
                    ),
                )
                batch_id = cursor.lastrowid
                if conn is None:
                    executor.commit()
                return batch_id
        finally:
            if conn is None:
                executor.close()

    def get_batch_by_id(self, batch_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[StockBatch]:
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            cursor.execute("SELECT * FROM stock_batches WHERE batch_id = ?;", (batch_id,))
            row = cursor.fetchone()
            return StockBatch(**dict(row)) if row else None
        finally:
            if conn is None:
                executor.close()

    def get_or_create_batch_for_sale(
        self,
        product_id: int,
        batch_id: Optional[int] = None,
        batch_no: Optional[str] = None,
        sale_qty: float = 1.0,
        sale_rate: float = 0.0,
        conn: Optional[sqlite3.Connection] = None,
    ) -> StockBatch:
        """
        Retrieves a valid stock batch for billing with stock availability validation.
        No phantom batch creation is allowed if stock is insufficient.
        """
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            if batch_id and batch_id > 0:
                cursor.execute("SELECT * FROM stock_batches WHERE batch_id = ?;", (batch_id,))
                row = cursor.fetchone()
                if row:
                    b = StockBatch(**dict(row))
                    if b.current_qty < sale_qty:
                        raise ValueError(f"निवडलेल्या बॅचमध्ये साठा अपुरा आहे (Insufficient batch stock: available {b.current_qty}, requested {sale_qty}).")
                    return b

            if batch_no and batch_no != "N/A":
                cursor.execute("SELECT * FROM stock_batches WHERE product_id = ? AND batch_no = ?;", (product_id, batch_no))
                row = cursor.fetchone()
                if row:
                    b = StockBatch(**dict(row))
                    if b.current_qty < sale_qty:
                        raise ValueError(f"निवडलेल्या बॅचमध्ये साठा अपुरा आहे (Insufficient batch stock: available {b.current_qty}, requested {sale_qty}).")
                    return b

            # Try active FEFO batch with sufficient quantity
            cursor.execute(
                """
                SELECT * FROM stock_batches 
                WHERE product_id = ? AND current_qty >= ? 
                ORDER BY 
                    CASE WHEN exp_date IS NULL OR exp_date = '' THEN 1 ELSE 0 END,
                    exp_date ASC,
                    batch_id ASC 
                LIMIT 1;
                """,
                (product_id, sale_qty),
            )
            row = cursor.fetchone()
            if row:
                return StockBatch(**dict(row))

            # Any batch with positive stock
            cursor.execute(
                "SELECT * FROM stock_batches WHERE product_id = ? AND current_qty > 0 ORDER BY current_qty DESC, batch_id ASC LIMIT 1;",
                (product_id,),
            )
            row = cursor.fetchone()
            if row:
                return StockBatch(**dict(row))

            # If no available stock batch exists, reject sale. NO PHANTOM BATCH CREATION!
            raise ValueError(f"उत्पादनासाठी साठा उपलब्ध नाही (Insufficient stock available for Product ID {product_id}).")
        finally:
            if conn is None:
                executor.close()

    def get_available_batches_fefo(self, product_id: int) -> List[StockBatch]:
        """
        Get all batches for a product with positive stock, sorted by FEFO (First Expired First Out).
        Batches with earlier expiry dates come first. Batches without expiry come last.
        """
        sql = """
            SELECT * FROM stock_batches
            WHERE product_id = ? AND current_qty > 0
            ORDER BY 
                CASE WHEN exp_date IS NULL OR exp_date = '' THEN 1 ELSE 0 END,
                exp_date ASC,
                batch_id ASC;
        """
        rows = self.db.fetch_all(sql, (product_id,))
        return [StockBatch(**dict(r)) for r in rows]

    def deduct_batch_stock(self, batch_id: int, qty_to_deduct: float, conn: Optional[sqlite3.Connection] = None) -> None:
        """Deduct quantity from a specific batch and verify it does not go negative."""
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            cursor.execute("SELECT current_qty, batch_no FROM stock_batches WHERE batch_id = ?;", (batch_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Batch ID {batch_id} not found in database.")
            
            curr_qty = float(row["current_qty"])
            if curr_qty < qty_to_deduct:
                raise ValueError(f"साठा अपुरा आहे (Insufficient stock in batch '{row['batch_no']}': available {curr_qty}, requested {qty_to_deduct}).")

            sql = "UPDATE stock_batches SET current_qty = current_qty - ? WHERE batch_id = ?;"
            cursor.execute(sql, (qty_to_deduct, batch_id))
            if conn is None:
                executor.commit()
        finally:
            if conn is None:
                executor.close()


    def add_batch_stock(self, batch_id: int, qty_to_add: float, conn: Optional[sqlite3.Connection] = None) -> None:
        """Add quantity back to a specific batch (e.g. on return or cancellation)."""
        sql = "UPDATE stock_batches SET current_qty = current_qty + ? WHERE batch_id = ?;"
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            cursor.execute(sql, (qty_to_add, batch_id))
            if conn is None:
                executor.commit()
        finally:
            if conn is None:
                executor.close()

    def record_stock_movement(self, entry: StockLedgerEntry, conn: Optional[sqlite3.Connection] = None) -> int:
        """Record an immutable stock movement entry in stock_ledger."""
        sql = """
            INSERT INTO stock_ledger (
                product_id, batch_id, transaction_type, reference_type,
                reference_id, qty_in, qty_out, balance_qty, rate, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            cursor.execute(
                sql,
                (
                    entry.product_id,
                    entry.batch_id,
                    entry.transaction_type,
                    entry.reference_type,
                    entry.reference_id,
                    entry.qty_in,
                    entry.qty_out,
                    entry.balance_qty,
                    entry.rate,
                    entry.remarks,
                ),
            )
            ledger_id = cursor.lastrowid
            if conn is None:
                executor.commit()
            return ledger_id
        finally:
            if conn is None:
                executor.close()

    def get_product_total_stock(self, product_id: int, conn: Optional[sqlite3.Connection] = None) -> float:
        """Calculate total current stock across all batches for a given product."""
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            cursor.execute("SELECT COALESCE(SUM(current_qty), 0) as total FROM stock_batches WHERE product_id = ?;", (product_id,))
            row = cursor.fetchone()
            return float(row["total"]) if row else 0.0
        finally:
            if conn is None:
                executor.close()


    def get_stock_inventory_summary(self, category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get complete stock report with product details, batch numbers, expiry dates, and valuations (including newly added catalog products)."""
        sql = """
            SELECT 
                p.product_id,
                p.product_name,
                p.hsn_code,
                c.category_name,
                m.manufacturer_name,
                u.symbol as unit_symbol,
                sb.batch_id,
                COALESCE(sb.batch_no, 'N/A') as batch_no,
                sb.mfg_date,
                sb.exp_date,
                COALESCE(sb.purchase_rate, p.default_purchase_rate, 0.0) as purchase_rate,
                COALESCE(sb.sale_rate, p.default_sale_rate, 0.0) as sale_rate,
                COALESCE(sb.mrp, p.default_mrp, 0.0) as mrp,
                COALESCE(sb.current_qty, 0.0) as current_qty,
                (COALESCE(sb.current_qty, 0.0) * COALESCE(sb.purchase_rate, p.default_purchase_rate, 0.0)) as purchase_value,
                (COALESCE(sb.current_qty, 0.0) * COALESCE(sb.sale_rate, p.default_sale_rate, 0.0)) as sale_value
            FROM products p
            LEFT JOIN stock_batches sb ON p.product_id = sb.product_id AND sb.current_qty > 0
            LEFT JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
            LEFT JOIN units u ON p.unit_id = u.unit_id
            WHERE p.is_active = 1 AND (? IS NULL OR p.category_id = ?)
            ORDER BY p.product_name ASC, sb.exp_date ASC;
        """
        rows = self.db.fetch_all(sql, (category_id, category_id))
        return [dict(r) for r in rows]

