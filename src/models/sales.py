"""
Domain Data Models for Sales Billing, Invoicing, and Sales Returns.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class SaleItem(BaseModel):
    sale_item_id: Optional[int] = None
    sale_id: Optional[int] = None
    product_id: int
    batch_id: Optional[int] = 0

    product_name: Optional[str] = None
    batch_no: Optional[str] = None
    exp_date: Optional[str] = None
    hsn_code: Optional[str] = None
    qty: float
    unit_id: Optional[int] = None
    unit_name: Optional[str] = None
    sale_rate: float
    mrp: float
    discount_percent: float = 0.0
    discount_amount: float = 0.0
    taxable_amount: float
    cgst_rate: float = 0.0
    cgst_amount: float = 0.0
    sgst_rate: float = 0.0
    sgst_amount: float = 0.0
    igst_rate: float = 0.0
    igst_amount: float = 0.0
    total_amount: float
    created_at: Optional[str] = None


class Sale(BaseModel):
    sale_id: Optional[int] = None
    invoice_no: str
    sale_date: str
    customer_id: int
    customer_name: Optional[str] = None
    customer_mobile: Optional[str] = None
    customer_village: Optional[str] = None
    customer_gstin: Optional[str] = None
    doctor_or_officer: Optional[str] = None
    payment_mode: str = "CASH"  # 'CASH', 'CREDIT', 'UPI', 'CARD', 'SPLIT'
    total_taxable: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_igst: float = 0.0
    total_discount: float = 0.0
    extra_charges: float = 0.0
    round_off: float = 0.0
    net_amount: float
    paid_amount: float = 0.0
    due_amount: float = 0.0
    print_count: int = 0
    remarks: Optional[str] = None
    items: List[SaleItem] = Field(default_factory=list)
    created_at: Optional[str] = None


class SalesReturnItem(BaseModel):
    return_item_id: Optional[int] = None
    return_id: Optional[int] = None
    product_id: int
    batch_id: Optional[int] = None
    qty: float
    sale_rate: float
    taxable_amount: float
    tax_amount: float = 0.0
    total_amount: float
    reason: Optional[str] = None


class SalesReturn(BaseModel):
    return_id: Optional[int] = None
    return_no: str
    return_date: str
    sale_id: Optional[int] = None
    customer_id: int
    total_taxable: float = 0.0
    total_tax: float = 0.0
    round_off: float = 0.0
    net_amount: float
    remarks: Optional[str] = None
    items: List[SalesReturnItem] = Field(default_factory=list)
    created_at: Optional[str] = None
