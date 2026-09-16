"""
Service Layer for Inward Purchase Processing, Stock Inwarding, and Supplier Accounting.
"""
from __future__ import annotations

from typing import Optional
from src.db.connection import DatabaseManager, get_db_manager
from src.models.accounting import LedgerEntry, Voucher
from src.models.inventory import StockBatch, StockLedgerEntry
from src.models.purchase import Purchase
from src.repositories.accounting_repository import AccountingRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.master_data_repository import MasterDataRepository
from src.repositories.purchase_repository import PurchaseRepository


class PurchaseService:
    """Business logic for inward purchase recording, batch updating, and accounting postings."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
        self.purchase_repo = PurchaseRepository(self.db)
        self.inventory_repo = InventoryRepository(self.db)
        self.master_repo = MasterDataRepository(self.db)
        self.accounting_repo = AccountingRepository(self.db)

    def process_inward_purchase(self, purchase: Purchase) -> int:
        """
        Processes inward purchase invoice atomically:
        1. Inserts purchase header & items.
        2. Upserts stock batches (increases stock by qty + free_qty).
        3. Records stock ledger entries.
        4. Updates supplier balance.
        5. Posts double-entry accounting vouchers.
        """
        with self.db.transaction() as conn:
            # 1. Persist Purchase Invoice
            purchase_id = self.purchase_repo.create_purchase(purchase, conn=conn)

            # 2 & 3. Update stock batches & record stock movements
            for item in purchase.items:
                total_inward_qty = item.qty + item.free_qty
                batch = StockBatch(
                    product_id=item.product_id,
                    batch_no=item.batch_no,
                    mfg_date=item.mfg_date,
                    exp_date=item.exp_date,
                    purchase_rate=item.purchase_rate,
                    sale_rate=item.sale_rate,
                    mrp=item.mrp,
                    current_qty=total_inward_qty,
                )
                batch_id = self.inventory_repo.upsert_batch(batch, conn=conn)

                # Get product current balance for ledger
                curr_stock = self.inventory_repo.get_product_total_stock(item.product_id, conn=conn)


                self.inventory_repo.record_stock_movement(
                    StockLedgerEntry(
                        product_id=item.product_id,
                        batch_id=batch_id,
                        transaction_type="PURCHASE",
                        reference_type="INVOICE",
                        reference_id=purchase_id,
                        qty_in=total_inward_qty,
                        qty_out=0.0,
                        balance_qty=curr_stock,
                        rate=item.purchase_rate,
                        remarks=f"Inward Inv: {purchase.invoice_no}",
                    ),
                    conn=conn,
                )

            # 4. Update Supplier Balance (Payable increases by unpaid due amount)
            unpaid_amount = purchase.net_amount - purchase.paid_amount
            if unpaid_amount > 0:
                self.master_repo.update_supplier_balance(purchase.supplier_id, unpaid_amount, conn=conn)

            # 5. Post Accounting Voucher
            self._post_purchase_voucher(purchase, purchase_id, conn)

            return purchase_id

    def _post_purchase_voucher(self, purchase: Purchase, purchase_id: int, conn) -> None:
        """Post double-entry voucher for purchase."""
        purchase_ac = self.accounting_repo.get_account_by_name("Purchase Account")
        cgst_in_ac = self.accounting_repo.get_account_by_name("CGST Input Account")
        sgst_in_ac = self.accounting_repo.get_account_by_name("SGST Input Account")
        igst_in_ac = self.accounting_repo.get_account_by_name("IGST Input Account")
        cash_ac = self.accounting_repo.get_account_by_name("Cash in Hand")
        bank_ac = self.accounting_repo.get_account_by_name("Bank Account")

        entries = []
        # Debit Purchase Account
        if purchase.total_taxable > 0:
            entries.append(
                LedgerEntry(
                    account_id=purchase_ac.account_id,
                    debit_amount=purchase.total_taxable,
                    credit_amount=0.0,
                    particulars=f"Purchase Inv {purchase.invoice_no}",
                )
            )

        # Debit Input GST
        if purchase.total_cgst > 0 and cgst_in_ac:
            entries.append(
                LedgerEntry(
                    account_id=cgst_in_ac.account_id,
                    debit_amount=purchase.total_cgst,
                    credit_amount=0.0,
                    particulars="Input CGST",
                )
            )
        if purchase.total_sgst > 0 and sgst_in_ac:
            entries.append(
                LedgerEntry(
                    account_id=sgst_in_ac.account_id,
                    debit_amount=purchase.total_sgst,
                    credit_amount=0.0,
                    particulars="Input SGST",
                )
            )
        if purchase.total_igst > 0 and igst_in_ac:
            entries.append(
                LedgerEntry(
                    account_id=igst_in_ac.account_id,
                    debit_amount=purchase.total_igst,
                    credit_amount=0.0,
                    particulars="Input IGST",
                )
            )

        # Credit Cash/Bank if paid, balance goes to Supplier liability
        if purchase.paid_amount > 0:
            pay_ac = cash_ac if purchase.payment_type == "CASH" else bank_ac
            entries.append(
                LedgerEntry(
                    account_id=pay_ac.account_id,
                    debit_amount=0.0,
                    credit_amount=purchase.paid_amount,
                    particulars="Paid for Purchase",
                )
            )

        due = purchase.net_amount - purchase.paid_amount
        if due > 0:
            # Credit Purchase Account / System Supplier mapping
            # In simple chart, unpaid balance maps directly to supplier account or general creditors
            entries.append(
                LedgerEntry(
                    account_id=purchase_ac.account_id,  # or Accounts Payable
                    debit_amount=0.0,
                    credit_amount=due,
                    particulars=f"Supplier Credit Due (Supp ID: {purchase.supplier_id})",
                )
            )

        # Verify entry balance before inserting
        tot_dr = sum(e.debit_amount for e in entries)
        tot_cr = sum(e.credit_amount for e in entries)
        if round(tot_dr, 2) == round(tot_cr, 2) and tot_dr > 0:
            vch_no = self.accounting_repo.generate_next_voucher_no("JOURNAL")
            vch = Voucher(
                voucher_no=vch_no,
                voucher_date=purchase.purchase_date,
                voucher_type="JOURNAL",
                total_amount=purchase.net_amount,
                narration=f"Purchase from Supplier #{purchase.supplier_id} Inv: {purchase.invoice_no}",
                reference_type="PURCHASE",
                reference_id=purchase_id,
                entries=entries,
            )
            self.accounting_repo.create_voucher(vch, conn=conn)
