"""
API Route Handlers for Sales, Billing POS, and PDF Invoicing.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from src.db.connection import get_db_manager
from src.models.sales import Sale, SaleItem, SalesReturn, SalesReturnItem


from src.printing.invoice_printer import InvoicePrinter
from src.repositories.master_data_repository import MasterDataRepository
from src.repositories.sales_repository import SalesRepository
from src.repositories.system_repository import SystemRepository
from src.services.sales_service import SalesService

router = APIRouter(prefix="/api/sales", tags=["Sales"])



class TaxCalculationRequest(BaseModel):
    qty: float
    rate: float
    discount_percent: float = 0.0
    cgst_rate: float = 0.0
    sgst_rate: float = 0.0
    igst_rate: float = 0.0
    is_rate_tax_inclusive: bool = True


@router.get("/next-invoice-no")
def get_next_invoice_no():
    repo = SalesRepository(get_db_manager())
    return {"next_invoice_no": repo.generate_next_invoice_no()}


@router.get("/next-return-no")
def get_next_return_no():
    repo = SalesRepository(get_db_manager())
    return {"next_return_no": repo.generate_next_return_no()}


@router.post("/calculate-tax")
def calculate_tax(req: TaxCalculationRequest):
    svc = SalesService(get_db_manager())
    result = svc.calculate_item_tax(
        qty=req.qty,
        rate=req.rate,
        discount_percent=req.discount_percent,
        cgst_rate=req.cgst_rate,
        sgst_rate=req.sgst_rate,
        igst_rate=req.igst_rate,
        is_rate_tax_inclusive=req.is_rate_tax_inclusive,
    )
    return result


@router.post("/create")
def create_sales_invoice(sale: Sale):
    svc = SalesService(get_db_manager())
    try:
        sale_id = svc.process_sales_invoice(sale)
        return {"success": True, "sale_id": sale_id, "invoice_no": sale.invoice_no}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/returns")
def create_sale_return(ret: SalesReturn):
    """Process customer sale return invoice."""
    svc = SalesService(get_db_manager())
    try:
        return_id = svc.process_sale_return(ret)
        return {"success": True, "return_id": return_id, "return_no": ret.return_no}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/returns")
def list_sale_returns():
    """List past sale returns."""
    repo = SalesRepository(get_db_manager())
    return repo.get_sale_returns_list()


@router.get("/returns/{return_id}")
def get_sale_return_detail(return_id: int):
    """Get sale return detail by return_id."""
    repo = SalesRepository(get_db_manager())
    ret = repo.get_sale_return_by_id(return_id)
    if not ret:
        raise HTTPException(status_code=404, detail="Sale return record not found")
    return ret


@router.get("/list")
def list_sales(from_date: Optional[str] = None, to_date: Optional[str] = None, customer_id: Optional[int] = None):
    repo = SalesRepository(get_db_manager())
    return repo.get_sales_list(from_date=from_date, to_date=to_date, customer_id=customer_id)


@router.get("/{sale_id}/eligible-returns")
def get_eligible_returns(sale_id: int):
    """Fetch eligible return items and quantities for a sale invoice."""
    repo = SalesRepository(get_db_manager())
    sale = repo.get_sale_by_id(sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale invoice not found")

    returned_map = repo.get_already_returned_qty_map(sale_id)
    eligible_items = []
    for item in sale.items:
        already_returned = returned_map.get(item.product_id, 0.0)
        eligible_qty = max(0.0, item.qty - already_returned)
        eligible_items.append({
            "product_id": item.product_id,
            "product_name": item.product_name,
            "batch_id": item.batch_id,
            "batch_no": item.batch_no,
            "sold_qty": item.qty,
            "already_returned_qty": already_returned,
            "eligible_return_qty": eligible_qty,
            "sale_rate": item.sale_rate,
            "mrp": item.mrp,
            "unit_name": item.unit_name,
        })
    return {"sale_id": sale_id, "invoice_no": sale.invoice_no, "customer_id": sale.customer_id, "items": eligible_items}


@router.get("/{sale_id}")
def get_sale_detail(sale_id: int):
    repo = SalesRepository(get_db_manager())
    sale = repo.get_sale_by_id(sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale invoice not found")
    return sale


@router.get("/{sale_id}/pdf")
def download_invoice_pdf(sale_id: int):
    repo = SalesRepository(get_db_manager())
    sys_repo = SystemRepository(get_db_manager())
    sale = repo.get_sale_by_id(sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale invoice not found")

    settings = sys_repo.get_company_settings()
    printer = InvoicePrinter(company_settings=settings)
    pdf_bytes = printer.generate_invoice_pdf(sale=sale)
    repo.increment_print_count(sale_id)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=Invoice_{sale.invoice_no}.pdf"},
    )

