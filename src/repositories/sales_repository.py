"""
Data Access Layer (Repository) for Sales Invoices and Sales Returns.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional
from src.models.sales import Sale, SaleItem, SalesReturn, SalesReturnItem
from src.repositories.base_repository import BaseRepository


class SalesRepository(BaseRepository):
    """Repository for managing sales billing, tax invoices, and sales returns."""

    def generate_next_invoice_no(self, prefix: str = "INV-") -> str:
        """Generate guaranteed unused sequential invoice number (e.g., INV-00001, INV-00002)."""
        rows = self.db.fetch_all("SELECT invoice_no FROM sales WHERE invoice_no LIKE ?;", (f"{prefix}%",))
        max_num = 0
        for r in rows:
            inv = str(r["invoice_no"])
            num_str = inv[len(prefix):]
            if num_str.isdigit():
                max_num = max(max_num, int(num_str))

        row = self.db.fetch_one("SELECT MAX(sale_id) as last_id FROM sales;")
        last_id = row["last_id"] if row and row["last_id"] else 0
        next_num = max(max_num + 1, last_id + 1, 1)

        while True:
            candidate = f"{prefix}{next_num:05d}"
            existing = self.db.fetch_one("SELECT 1 FROM sales WHERE invoice_no = ?;", (candidate,))
            if not existing:
                return candidate
            next_num += 1

    def generate_next_return_no(self, prefix: str = "RET-") -> str:
        """Generate sequential sales return number."""
        rows = self.db.fetch_all("SELECT return_no FROM sales_returns WHERE return_no LIKE ?;", (f"{prefix}%",))
        max_num = 0
        for r in rows:
            ret = str(r["return_no"])
            num_str = ret[len(prefix):]
            if num_str.isdigit():
                max_num = max(max_num, int(num_str))

        row = self.db.fetch_one("SELECT MAX(return_id) as last_id FROM sales_returns;")
        last_id = row["last_id"] if row and row["last_id"] else 0
        next_num = max(max_num + 1, last_id + 1, 1)

        while True:
            candidate = f"{prefix}{next_num:05d}"
            existing = self.db.fetch_one("SELECT 1 FROM sales_returns WHERE return_no = ?;", (candidate,))
            if not existing:
                return candidate
            next_num += 1

    def create_sale(self, sale: Sale, conn: Optional[sqlite3.Connection] = None) -> int:
        """Persist sales invoice header and line items."""
        executor = conn if conn is not None else self.db.get_connection()
        cursor = executor.cursor()

        # Guarantee unique invoice number
        if not sale.invoice_no:
            sale.invoice_no = self.generate_next_invoice_no()
        else:
            cursor.execute("SELECT 1 FROM sales WHERE invoice_no = ?;", (sale.invoice_no,))
            if cursor.fetchone():
                sale.invoice_no = self.generate_next_invoice_no()

        sql_head = """
            INSERT INTO sales (
                invoice_no, sale_date, customer_id, doctor_or_officer, payment_mode,
                total_taxable, total_cgst, total_sgst, total_igst, total_discount,
                extra_charges, round_off, net_amount, paid_amount, due_amount,
                print_count, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        sql_item = """
            INSERT INTO sale_items (
                sale_id, product_id, batch_id, qty, unit_id,
                sale_rate, mrp, discount_percent, discount_amount, taxable_amount,
                cgst_rate, cgst_amount, sgst_rate, sgst_amount, igst_rate, igst_amount,
                total_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        try:
            cursor.execute(
                sql_head,
                (
                    sale.invoice_no,
                    sale.sale_date,
                    sale.customer_id,
                    sale.doctor_or_officer,
                    sale.payment_mode,
                    sale.total_taxable,
                    sale.total_cgst,
                    sale.total_sgst,
                    sale.total_igst,
                    sale.total_discount,
                    sale.extra_charges,
                    sale.round_off,
                    sale.net_amount,
                    sale.paid_amount,
                    sale.due_amount,
                    sale.print_count,
                    sale.remarks,
                ),
            )
            sale_id = cursor.lastrowid

            for item in sale.items:
                cursor.execute(
                    sql_item,
                    (
                        sale_id,
                        item.product_id,
                        item.batch_id,
                        item.qty,
                        item.unit_id,
                        item.sale_rate,
                        item.mrp,
                        item.discount_percent,
                        item.discount_amount,
                        item.taxable_amount,
                        item.cgst_rate,
                        item.cgst_amount,
                        item.sgst_rate,
                        item.sgst_amount,
                        item.igst_rate,
                        item.igst_amount,
                        item.total_amount,
                    ),
                )

            if conn is None:
                executor.commit()
            return sale_id
        finally:
            if conn is None:
                executor.close()

    def get_sale_by_id(self, sale_id: int) -> Optional[Sale]:
        """Fetch complete sale invoice with customer details and line items."""
        sql_sale = """
            SELECT 
                s.*,
                c.customer_name,
                c.mobile as customer_mobile,
                c.village as customer_village,
                c.gstin as customer_gstin
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            WHERE s.sale_id = ?;
        """
        row = self.db.fetch_one(sql_sale, (sale_id,))
        if not row:
            return None

        sale_dict = dict(row)
        sql_items = """
            SELECT 
                si.*,
                p.product_name,
                p.hsn_code,
                sb.batch_no,
                sb.exp_date,
                u.symbol as unit_name
            FROM sale_items si
            JOIN products p ON si.product_id = p.product_id
            JOIN stock_batches sb ON si.batch_id = sb.batch_id
            LEFT JOIN units u ON si.unit_id = u.unit_id
            WHERE si.sale_id = ?
            ORDER BY si.sale_item_id ASC;
        """
        item_rows = self.db.fetch_all(sql_items, (sale_id,))
        sale_dict["items"] = [SaleItem(**dict(ir)) for ir in item_rows]
        return Sale(**sale_dict)

    def get_sales_list(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        customer_id: Optional[int] = None,
        payment_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get list of sales invoices with customer summary."""
        sql = """
            SELECT 
                s.*,
                c.customer_name,
                c.village,
                c.mobile
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            WHERE (? IS NULL OR s.sale_date >= ?)
              AND (? IS NULL OR s.sale_date <= ?)
              AND (? IS NULL OR s.customer_id = ?)
              AND (? IS NULL OR s.payment_mode = ?)
            ORDER BY s.sale_date DESC, s.sale_id DESC;
        """
        rows = self.db.fetch_all(
            sql,
            (from_date, from_date, to_date, to_date, customer_id, customer_id, payment_mode, payment_mode),
        )
        return [dict(r) for r in rows]

    def increment_print_count(self, sale_id: int) -> None:
        """Increment reprint count."""
        with self.db.transaction() as conn:
            conn.execute("UPDATE sales SET print_count = print_count + 1 WHERE sale_id = ?;", (sale_id,))

    def get_already_returned_qty_map(self, sale_id: int, conn: Optional[sqlite3.Connection] = None) -> Dict[int, float]:
        """Returns map of {product_id: total_returned_qty} for a specific sale_id."""
        executor = conn if conn is not None else self.db.get_connection()
        try:
            cursor = executor.cursor()
            sql = """
                SELECT sri.product_id, COALESCE(SUM(sri.qty), 0) as total_returned
                FROM sales_return_items sri
                JOIN sales_returns sr ON sri.return_id = sr.return_id
                WHERE sr.sale_id = ?
                GROUP BY sri.product_id;
            """
            cursor.execute(sql, (sale_id,))
            rows = cursor.fetchall()
            return {int(r["product_id"]): float(r["total_returned"]) for r in rows}
        finally:
            if conn is None:
                executor.close()

    def create_sale_return(self, ret: SalesReturn, conn: Optional[sqlite3.Connection] = None) -> int:
        """Persist sales return header and line items."""
        executor = conn if conn is not None else self.db.get_connection()
        cursor = executor.cursor()

        if not ret.return_no:
            ret.return_no = self.generate_next_return_no()
        else:
            cursor.execute("SELECT 1 FROM sales_returns WHERE return_no = ?;", (ret.return_no,))
            if cursor.fetchone():
                ret.return_no = self.generate_next_return_no()

        sql_head = """
            INSERT INTO sales_returns (
                return_no, return_date, sale_id, customer_id,
                total_taxable, total_tax, round_off, net_amount, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        sql_item = """
            INSERT INTO sales_return_items (
                return_id, product_id, batch_id, qty, sale_rate,
                taxable_amount, tax_amount, total_amount, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        try:
            cursor.execute(
                sql_head,
                (
                    ret.return_no,
                    ret.return_date,
                    ret.sale_id,
                    ret.customer_id,
                    ret.total_taxable,
                    ret.total_tax,
                    ret.round_off,
                    ret.net_amount,
                    ret.remarks,
                ),
            )
            return_id = cursor.lastrowid

            for item in ret.items:
                cursor.execute(
                    sql_item,
                    (
                        return_id,
                        item.product_id,
                        item.batch_id,
                        item.qty,
                        item.sale_rate,
                        item.taxable_amount,
                        item.tax_amount,
                        item.total_amount,
                        item.reason,
                    ),
                )

            if conn is None:
                executor.commit()
            return return_id
        finally:
            if conn is None:
                executor.close()

    def get_sale_return_by_id(self, return_id: int) -> Optional[Dict[str, Any]]:
        """Fetch sale return header and items detail."""
        sql_head = """
            SELECT 
                sr.*,
                c.customer_name,
                c.mobile as customer_mobile,
                s.invoice_no as original_invoice_no
            FROM sales_returns sr
            JOIN customers c ON sr.customer_id = c.customer_id
            LEFT JOIN sales s ON sr.sale_id = s.sale_id
            WHERE sr.return_id = ?;
        """
        row = self.db.fetch_one(sql_head, (return_id,))
        if not row:
            return None

        ret_dict = dict(row)
        sql_items = """
            SELECT 
                sri.*,
                p.product_name,
                sb.batch_no
            FROM sales_return_items sri
            JOIN products p ON sri.product_id = p.product_id
            LEFT JOIN stock_batches sb ON sri.batch_id = sb.batch_id
            WHERE sri.return_id = ?;
        """
        items = self.db.fetch_all(sql_items, (return_id,))
        ret_dict["items"] = [dict(i) for i in items]
        return ret_dict

    def get_sale_returns_list(self) -> List[Dict[str, Any]]:
        """Fetch list of all past sale returns."""
        sql = """
            SELECT 
                sr.*,
                c.customer_name,
                s.invoice_no as original_invoice_no
            FROM sales_returns sr
            JOIN customers c ON sr.customer_id = c.customer_id
            LEFT JOIN sales s ON sr.sale_id = s.sale_id
            ORDER BY sr.return_date DESC, sr.return_id DESC;
        """
        rows = self.db.fetch_all(sql)
        return [dict(r) for r in rows]

