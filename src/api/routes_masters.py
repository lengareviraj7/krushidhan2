"""
API Route Handlers for Master Data Entities (Products, Customers, Suppliers, Categories, Units).
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from src.db.connection import get_db_manager
from src.models.master_data import Category, Crop, Customer, Manufacturer, Product, Supplier, Unit
from src.repositories.master_data_repository import MasterDataRepository

router = APIRouter(prefix="/api/masters", tags=["Masters"])


@router.get("/all")
def get_all_lookup_data():
    repo = MasterDataRepository(get_db_manager())
    return {
        "categories": repo.get_all_categories(),
        "manufacturers": repo.get_all_manufacturers(),
        "units": repo.get_all_units(),
        "tax_groups": repo.get_all_tax_groups(),
        "crops": repo.get_all_crops(),
    }


@router.post("/manufacturers")
def create_manufacturer(mfg: Manufacturer):
    repo = MasterDataRepository(get_db_manager())
    try:
        mfg_id = repo.get_or_create_manufacturer(mfg.manufacturer_name, mfg.contact_person, mfg.mobile, mfg.address)
        return {"success": True, "manufacturer_id": mfg_id, "manufacturer_name": mfg.manufacturer_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/units")
def create_unit(unit: Unit):
    repo = MasterDataRepository(get_db_manager())
    try:
        unit_id = repo.create_unit(unit)
        return {"success": True, "unit_id": unit_id, "unit_name": unit.unit_name, "symbol": unit.symbol or unit.unit_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products")
def list_products(query: str = ""):
    repo = MasterDataRepository(get_db_manager())
    return repo.search_products(query)


@router.post("/products")
def create_product(product: Product):
    repo = MasterDataRepository(get_db_manager())
    try:
        prod_id = repo.create_product(product)
        return {"success": True, "product_id": prod_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers")
def list_customers(query: str = ""):
    repo = MasterDataRepository(get_db_manager())
    return repo.search_customers(query)


@router.get("/farmers/status-list")
def get_farmers_status(query: str = "", village: str = "", only_credit: bool = False):
    repo = MasterDataRepository(get_db_manager())
    return repo.get_farmers_status_list(query=query, village=village, only_credit=only_credit)


@router.get("/farmers/{customer_id}/statement")
def get_farmer_statement(customer_id: int):
    repo = MasterDataRepository(get_db_manager())
    statement = repo.get_farmer_statement(customer_id)
    if not statement:
        raise HTTPException(status_code=404, detail="Farmer customer not found")
    return statement


@router.get("/farmers/villages")
def get_farmer_villages():
    repo = MasterDataRepository(get_db_manager())
    return repo.get_distinct_villages()


@router.post("/customers")
def create_customer(customer: Customer):
    repo = MasterDataRepository(get_db_manager())
    try:
        cust_id = repo.create_customer(customer)
        return {"success": True, "customer_id": cust_id, "customer_name": customer.customer_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/suppliers")
def list_suppliers(query: str = ""):
    repo = MasterDataRepository(get_db_manager())
    return repo.search_suppliers(query)


@router.post("/suppliers")
def create_supplier(supplier: Supplier):
    repo = MasterDataRepository(get_db_manager())
    try:
        supp_id = repo.create_supplier(supplier)
        return {"success": True, "supplier_id": supp_id, "supplier_name": supplier.supplier_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
