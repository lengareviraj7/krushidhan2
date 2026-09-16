"""
Cloud Database Persistence & Hydration Manager for Vercel Serverless Functions.
Ensures that data created on ephemeral Vercel containers is permanently saved
to Cloud Storage (MongoDB Atlas / Persistent Remote Storage) and restored on cold starts.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agri_erp.cloud_sync")

try:
    import pymongo
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


class CloudSyncManager:
    """Manages multi-device cloud persistence and serverless container hydration."""

    def __init__(self, mongo_uri: Optional[str] = None):
        self.mongo_uri = mongo_uri or os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
        self.db_name = os.environ.get("MONGODB_DB_NAME", "krushidhan_erp")
        self._client: Any = None
        self._db: Any = None

        if HAS_PYMONGO and self.mongo_uri:
            try:
                self._client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
                self._db = self._client[self.db_name]
                logger.info("Connected to MongoDB Cloud for persistent Vercel storage.")
            except Exception as e:
                logger.warning(f"Could not connect to MongoDB: {e}")

    @property
    def is_cloud_enabled(self) -> bool:
        return self._db is not None

    def hydrate_sqlite_from_cloud(self, conn: sqlite3.Connection) -> bool:
        """Restores missing records from MongoDB into local SQLite database on cold start."""
        if not self.is_cloud_enabled:
            return False

        try:
            cur = conn.cursor()

            # 1. Hydrate Products
            products_col = self._db["products"]
            mongo_products = list(products_col.find())
            for p in mongo_products:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO products (
                        product_id, product_name, category_id, manufacturer_id, hsn_code,
                        unit_id, tax_group_id, default_purchase_rate, default_sale_rate,
                        default_mrp, min_stock_alert, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        p.get("product_id"), p.get("product_name"), p.get("category_id"),
                        p.get("manufacturer_id"), p.get("hsn_code"), p.get("unit_id"),
                        p.get("tax_group_id"), p.get("default_purchase_rate"),
                        p.get("default_sale_rate"), p.get("default_mrp"),
                        p.get("min_stock_alert", 5.0), p.get("is_active", 1)
                    )
                )

            # 2. Hydrate Stock Batches
            batches_col = self._db["stock_batches"]
            mongo_batches = list(batches_col.find())
            for b in mongo_batches:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO stock_batches (
                        batch_id, product_id, batch_no, current_qty, purchase_rate,
                        sale_rate, mrp, mfg_date, exp_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        b.get("batch_id"), b.get("product_id"), b.get("batch_no"),
                        b.get("current_qty"), b.get("purchase_rate"), b.get("sale_rate"),
                        b.get("mrp"), b.get("mfg_date"), b.get("exp_date")
                    )
                )

            # 3. Hydrate Customers
            cust_col = self._db["customers"]
            mongo_custs = list(cust_col.find())
            for c in mongo_custs:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO customers (
                        customer_id, customer_name, mobile, village, taluka, district,
                        aadhar_no, credit_limit, current_balance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        c.get("customer_id"), c.get("customer_name"), c.get("mobile"),
                        c.get("village"), c.get("taluka"), c.get("district"),
                        c.get("aadhar_no"), c.get("credit_limit"), c.get("current_balance")
                    )
                )

            # 4. Hydrate Sales Invoices
            sales_col = self._db["sales"]
            mongo_sales = list(sales_col.find())
            for s in mongo_sales:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO sales (
                        sale_id, invoice_no, sale_date, customer_id, doctor_or_officer,
                        payment_mode, total_taxable, total_cgst, total_sgst, total_igst,
                        total_discount, round_off, net_amount, paid_amount, due_amount, remarks
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        s.get("sale_id"), s.get("invoice_no"), s.get("sale_date"),
                        s.get("customer_id"), s.get("doctor_or_officer"), s.get("payment_mode"),
                        s.get("total_taxable"), s.get("total_cgst"), s.get("total_sgst"),
                        s.get("total_igst"), s.get("total_discount"), s.get("round_off"),
                        s.get("net_amount"), s.get("paid_amount"), s.get("due_amount"),
                        s.get("remarks")
                    )
                )

            conn.commit()
            cur.close()
            logger.info("Database hydration from Cloud complete.")
            return True
        except Exception as e:
            logger.error(f"Error hydrating SQLite from Cloud: {e}")
            return False

    def sync_record_to_cloud(self, collection_name: str, key_field: str, record: Dict[str, Any]) -> bool:
        """Pushes a modified record to Cloud MongoDB storage."""
        if not self.is_cloud_enabled:
            return False

        try:
            col = self._db[collection_name]
            key_val = record.get(key_field)
            if key_val is not None:
                col.replace_one({key_field: key_val}, record, upsert=True)
                return True
        except Exception as e:
            logger.error(f"Failed to sync {collection_name} record to Cloud: {e}")
        return False


_global_cloud_sync: Optional[CloudSyncManager] = None

def get_cloud_sync_manager() -> CloudSyncManager:
    global _global_cloud_sync
    if _global_cloud_sync is None:
        _global_cloud_sync = CloudSyncManager()
    return _global_cloud_sync
