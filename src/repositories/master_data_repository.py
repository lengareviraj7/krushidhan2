"""
Data Access Layer (Repositories) for Master Data Entities.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional
from src.models.master_data import (
    Category,
    Crop,
    Customer,
    CustomerGroup,
    ExtraCharge,
    Manufacturer,
    Product,
    Supplier,
    TaxGroup,
    Unit,
)
from src.repositories.base_repository import BaseRepository


class MasterDataRepository(BaseRepository):
    """Unified repository for master lookup entities."""

    # ---------------- Category CRUD ----------------
    def create_category(self, cat: Category) -> int:
        sql = "INSERT INTO categories (category_name, short_name, is_hardware_category) VALUES (?, ?, ?);"
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (cat.category_name, cat.short_name, cat.is_hardware_category))
            return cursor.lastrowid

    def get_all_categories(self) -> List[Category]:
        rows = self.db.fetch_all("SELECT * FROM categories ORDER BY category_name ASC;")
        return [Category(**dict(r)) for r in rows]

    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        row = self.db.fetch_one("SELECT * FROM categories WHERE category_id = ?;", (category_id,))
        return Category(**dict(row)) if row else None

    # ---------------- Manufacturer CRUD ----------------
    def create_manufacturer(self, mfg: Manufacturer) -> int:
        return self.get_or_create_manufacturer(mfg.manufacturer_name, mfg.contact_person, mfg.mobile, mfg.address)

    def get_or_create_manufacturer(self, manufacturer_name: str, contact_person: Optional[str] = None, mobile: Optional[str] = None, address: Optional[str] = None) -> int:
        name_clean = manufacturer_name.strip()
        existing = self.db.fetch_one("SELECT manufacturer_id FROM manufacturers WHERE LOWER(manufacturer_name) = LOWER(?);", (name_clean,))
        if existing:
            return existing['manufacturer_id']
        sql = "INSERT INTO manufacturers (manufacturer_name, contact_person, mobile, address) VALUES (?, ?, ?, ?);"
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (name_clean, contact_person, mobile, address))
            return cursor.lastrowid

    def get_all_manufacturers(self) -> List[Manufacturer]:
        rows = self.db.fetch_all("SELECT * FROM manufacturers ORDER BY manufacturer_name ASC;")
        return [Manufacturer(**dict(r)) for r in rows]

    def get_manufacturer_by_id(self, manufacturer_id: int) -> Optional[Manufacturer]:
        row = self.db.fetch_one("SELECT * FROM manufacturers WHERE manufacturer_id = ?;", (manufacturer_id,))
        return Manufacturer(**dict(row)) if row else None

    # ---------------- Units & Tax Groups ----------------
    def get_all_units(self) -> List[Unit]:
        rows = self.db.fetch_all("SELECT * FROM units ORDER BY unit_name ASC;")
        return [Unit(**dict(r)) for r in rows]

    def create_unit(self, unit: Unit) -> int:
        name_clean = unit.unit_name.strip()
        symbol_clean = (unit.symbol or name_clean).strip()
        existing = self.db.fetch_one("SELECT unit_id FROM units WHERE LOWER(unit_name) = LOWER(?) OR LOWER(symbol) = LOWER(?);", (name_clean, symbol_clean))
        if existing:
            return existing['unit_id']
        sql = "INSERT INTO units (unit_name, symbol) VALUES (?, ?);"
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (name_clean, symbol_clean))
            return cursor.lastrowid

    def get_all_tax_groups(self) -> List[TaxGroup]:
        rows = self.db.fetch_all("SELECT * FROM tax_groups WHERE is_active = 1 ORDER BY tax_group_id ASC;")
        return [TaxGroup(**dict(r)) for r in rows]

    def get_tax_group_by_id(self, tax_group_id: int) -> Optional[TaxGroup]:
        row = self.db.fetch_one("SELECT * FROM tax_groups WHERE tax_group_id = ?;", (tax_group_id,))
        return TaxGroup(**dict(row)) if row else None

    # ---------------- Crops ----------------
    def create_crop(self, crop: Crop) -> int:
        sql = "INSERT INTO crops (crop_name, description) VALUES (?, ?);"
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (crop.crop_name, crop.description))
            return cursor.lastrowid

    def get_all_crops(self) -> List[Crop]:
        rows = self.db.fetch_all("SELECT * FROM crops ORDER BY crop_name ASC;")
        return [Crop(**dict(r)) for r in rows]

    # ---------------- Products CRUD ----------------
    def create_product(self, prod: Product) -> int:
        sql = """
            INSERT INTO products (
                product_name, category_id, manufacturer_id, hsn_code, unit_id,
                tax_group_id, default_purchase_rate, default_sale_rate, default_mrp,
                min_stock_alert, crop_id, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    prod.product_name,
                    prod.category_id,
                    prod.manufacturer_id,
                    prod.hsn_code,
                    prod.unit_id,
                    prod.tax_group_id,
                    prod.default_purchase_rate,
                    prod.default_sale_rate,
                    prod.default_mrp,
                    prod.min_stock_alert,
                    prod.crop_id,
                    prod.is_active,
                ),
            )
            return cursor.lastrowid

    def update_product(self, prod: Product) -> None:
        sql = """
            UPDATE products SET
                product_name = ?, category_id = ?, manufacturer_id = ?, hsn_code = ?,
                unit_id = ?, tax_group_id = ?, default_purchase_rate = ?,
                default_sale_rate = ?, default_mrp = ?, min_stock_alert = ?,
                crop_id = ?, is_active = ?
            WHERE product_id = ?;
        """
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    prod.product_name,
                    prod.category_id,
                    prod.manufacturer_id,
                    prod.hsn_code,
                    prod.unit_id,
                    prod.tax_group_id,
                    prod.default_purchase_rate,
                    prod.default_sale_rate,
                    prod.default_mrp,
                    prod.min_stock_alert,
                    prod.crop_id,
                    prod.is_active,
                    prod.product_id,
                ),
            )

    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        row = self.db.fetch_one("SELECT * FROM products WHERE product_id = ?;", (product_id,))
        return Product(**dict(row)) if row else None

    def search_products(self, query: str = "") -> List[dict]:
        """Search products with category, manufacturer, and current stock information."""
        sql = """
            SELECT 
                p.*, 
                c.category_name, 
                m.manufacturer_name, 
                u.symbol as unit_symbol,
                tg.cgst_rate, tg.sgst_rate, tg.igst_rate,
                COALESCE(SUM(sb.current_qty), 0) as total_stock
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
            LEFT JOIN units u ON p.unit_id = u.unit_id
            LEFT JOIN tax_groups tg ON p.tax_group_id = tg.tax_group_id
            LEFT JOIN stock_batches sb ON p.product_id = sb.product_id
            WHERE p.is_active = 1 AND (p.product_name LIKE ? OR p.hsn_code LIKE ? OR m.manufacturer_name LIKE ?)
            GROUP BY p.product_id
            ORDER BY p.product_name ASC;
        """
        pattern = f"%{query}%"
        rows = self.db.fetch_all(sql, (pattern, pattern, pattern))
        return [dict(r) for r in rows]

    # ---------------- Customers CRUD ----------------
    def create_customer(self, cust: Customer) -> int:
        sql = """
            INSERT INTO customers (
                customer_name, mobile, village, taluka, district, state,
                aadhar_no, gstin, group_id, opening_balance, current_balance,
                credit_limit, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    cust.customer_name,
                    cust.mobile,
                    cust.village,
                    cust.taluka,
                    cust.district,
                    cust.state,
                    cust.aadhar_no,
                    cust.gstin,
                    cust.group_id,
                    cust.opening_balance,
                    cust.opening_balance,  # current_balance starts at opening_balance
                    cust.credit_limit,
                    cust.is_active,
                ),
            )
            return cursor.lastrowid

    def get_customer_by_id(self, customer_id: int) -> Optional[Customer]:
        row = self.db.fetch_one("SELECT * FROM customers WHERE customer_id = ?;", (customer_id,))
        return Customer(**dict(row)) if row else None

    def search_customers(self, query: str = "") -> List[Customer]:
        sql = """
            SELECT * FROM customers
            WHERE is_active = 1 AND (customer_name LIKE ? OR mobile LIKE ? OR village LIKE ?)
            ORDER BY customer_name ASC;
        """
        pattern = f"%{query}%"
        rows = self.db.fetch_all(sql, (pattern, pattern, pattern))
        return [Customer(**dict(r)) for r in rows]

    def get_farmers_status_list(
        self, query: str = "", village: str = "", only_credit: bool = False
    ) -> List[dict]:
        """
        Aggregated list of all farmers with total purchase bills, total purchases amount,
        total paid, and current pending credit balance.
        """
        sql = """
            SELECT 
                c.customer_id,
                c.customer_name,
                c.mobile,
                COALESCE(c.village, 'Local') as village,
                c.taluka,
                c.current_balance,
                COUNT(s.sale_id) as total_bills_count,
                COALESCE(SUM(s.net_amount), 0) as total_purchases_amount,
                COALESCE(SUM(s.paid_amount), 0) as total_paid_amount
            FROM customers c
            LEFT JOIN sales s ON c.customer_id = s.customer_id
            WHERE c.is_active = 1
              AND (? = '' OR c.customer_name LIKE ? OR c.mobile LIKE ?)
              AND (? = '' OR c.village LIKE ?)
              AND (? = 0 OR c.current_balance > 0)
            GROUP BY c.customer_id
            ORDER BY 
                CASE WHEN ? = 1 THEN c.current_balance ELSE 0 END DESC,
                c.customer_name ASC;
        """
        name_pat = f"%{query}%" if query else ""
        vill_pat = f"%{village}%" if village else ""
        credit_flag = 1 if only_credit else 0

        rows = self.db.fetch_all(
            sql,
            (query, name_pat, name_pat, village, vill_pat, credit_flag, credit_flag),
        )
        return [dict(r) for r in rows]

    def get_farmer_statement(self, customer_id: int) -> Optional[dict]:
        """
        Returns full profile and history for a farmer:
        - Customer details
        - Invoices with itemized line items (products, batches, qty, rates)
        - Payment receipts
        """
        cust = self.get_customer_by_id(customer_id)
        if not cust:
            return None

        # 1. Fetch Invoices with line items
        sql_sales = """
            SELECT 
                s.sale_id,
                s.invoice_no,
                s.sale_date,
                s.payment_mode,
                s.net_amount,
                s.paid_amount,
                s.due_amount,
                s.remarks
            FROM sales s
            WHERE s.customer_id = ?
            ORDER BY s.sale_date DESC, s.sale_id DESC;
        """
        sales_rows = self.db.fetch_all(sql_sales, (customer_id,))
        invoices = []

        sql_items = """
            SELECT 
                si.sale_item_id,
                p.product_name,
                sb.batch_no,
                sb.exp_date,
                si.qty,
                u.symbol as unit_symbol,
                si.sale_rate,
                si.total_amount
            FROM sale_items si
            JOIN products p ON si.product_id = p.product_id
            JOIN stock_batches sb ON si.batch_id = sb.batch_id
            LEFT JOIN units u ON si.unit_id = u.unit_id
            WHERE si.sale_id = ?
            ORDER BY si.sale_item_id ASC;
        """

        for sr in sales_rows:
            inv_dict = dict(sr)
            item_rows = self.db.fetch_all(sql_items, (inv_dict["sale_id"],))
            inv_dict["items"] = [dict(ir) for ir in item_rows]
            invoices.append(inv_dict)

        # 2. Fetch Payment Receipts
        sql_receipts = """
            SELECT 
                v.voucher_id,
                v.voucher_no,
                v.voucher_date,
                v.total_amount,
                v.narration
            FROM vouchers v
            WHERE v.reference_id = ? AND v.voucher_type = 'RECEIPT'
            ORDER BY v.voucher_date DESC, v.voucher_id DESC;
        """
        receipt_rows = self.db.fetch_all(sql_receipts, (customer_id,))

        return {
            "customer": cust.model_dump(),
            "invoices": invoices,
            "receipts": [dict(rr) for rr in receipt_rows],
        }

    def get_distinct_villages(self) -> List[str]:
        """Fetch distinct non-empty village names for dropdown filter."""
        rows = self.db.fetch_all(
            "SELECT DISTINCT village FROM customers WHERE village IS NOT NULL AND village != '' ORDER BY village ASC;"
        )
        return [r["village"] for r in rows]

    def update_customer_balance(self, customer_id: int, delta_amount: float, conn: Optional[sqlite3.Connection] = None) -> None:
        """Update customer balance (positive for debit/increase in receivable, negative for payment)."""
        sql = "UPDATE customers SET current_balance = current_balance + ? WHERE customer_id = ?;"
        if conn is not None:
            conn.execute(sql, (delta_amount, customer_id))
        else:
            with self.db.transaction() as c:
                c.execute(sql, (delta_amount, customer_id))

    # ---------------- Suppliers CRUD ----------------
    def create_supplier(self, supp: Supplier) -> int:
        sql = """
            INSERT INTO suppliers (
                supplier_name, contact_person, mobile, email, address, city,
                state, gstin, pan, dl_number, bank_name, account_no, ifsc_code,
                opening_balance, current_balance, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    supp.supplier_name,
                    supp.contact_person,
                    supp.mobile,
                    supp.email,
                    supp.address,
                    supp.city,
                    supp.state,
                    supp.gstin,
                    supp.pan,
                    supp.dl_number,
                    supp.bank_name,
                    supp.account_no,
                    supp.ifsc_code,
                    supp.opening_balance,
                    supp.opening_balance,
                    supp.is_active,
                ),
            )
            return cursor.lastrowid

    def get_supplier_by_id(self, supplier_id: int) -> Optional[Supplier]:
        row = self.db.fetch_one("SELECT * FROM suppliers WHERE supplier_id = ?;", (supplier_id,))
        return Supplier(**dict(row)) if row else None

    def search_suppliers(self, query: str = "") -> List[Supplier]:
        sql = """
            SELECT * FROM suppliers
            WHERE is_active = 1 AND (supplier_name LIKE ? OR mobile LIKE ? OR city LIKE ?)
            ORDER BY supplier_name ASC;
        """
        pattern = f"%{query}%"
        rows = self.db.fetch_all(sql, (pattern, pattern, pattern))
        return [Supplier(**dict(r)) for r in rows]

    def update_supplier_balance(self, supplier_id: int, delta_amount: float, conn: Optional[sqlite3.Connection] = None) -> None:
        """Update supplier balance (positive for increase in liability/payable, negative for payment)."""
        sql = "UPDATE suppliers SET current_balance = current_balance + ? WHERE supplier_id = ?;"
        if conn is not None:
            conn.execute(sql, (delta_amount, supplier_id))
        else:
            with self.db.transaction() as c:
                c.execute(sql, (delta_amount, supplier_id))
