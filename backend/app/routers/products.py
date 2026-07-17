"""Real product management: full CRUD with search / filter / sort / pagination (§6)."""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

from ..database import get_db, next_seq, oid
from ..models import (Business, Product, StockAdjustment, Supplier, effective_price,
                      find_models, get_owned, insert_model, sale_active, to_dt)
from ..security import get_current_business

router = APIRouter(prefix="/api/products", tags=["products"])

SORTABLE = {"name", "category", "price", "cost", "stock", "daily_demand", "brand", "sku"}


class ProductIn(BaseModel):
    # basic information
    name: str = Field(min_length=1, max_length=255)
    sku: str | None = None
    barcode: str | None = None
    brand: str | None = None
    category: str = "General"
    subcategory: str | None = None
    description: str | None = None
    unit_type: str | None = None
    unit_size: str | None = None
    # pricing
    price: float = Field(gt=0, description="Current selling price")
    cost: float = Field(ge=0, description="Cost price")
    mrp: float | None = Field(default=None, ge=0)
    tax_rate: float | None = Field(default=None, ge=0, le=100)
    # inventory
    stock: int = Field(default=0, ge=0)
    min_stock: int | None = Field(default=None, ge=0)
    max_stock: int | None = Field(default=None, ge=0)
    safety_stock: int | None = Field(default=None, ge=0)
    reorder_level: int = Field(default=15, ge=0)
    reorder_qty: int | None = Field(default=None, ge=0)
    daily_demand: float = Field(default=5, ge=0)
    # supplier
    supplier_id: str | None = None
    supplier_cost: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    moq: int | None = Field(default=None, ge=0)
    # behaviour
    expiry_days: int = Field(default=0, ge=0, description="Shelf life in days; 0 = non-perishable")
    storage_type: str | None = None
    shelf_location: str | None = None

    @field_validator("mrp")
    @classmethod
    def mrp_covers_price(cls, v, info):
        if v is not None and v > 0 and "price" in info.data and v < info.data["price"]:
            raise ValueError("MRP cannot be below the selling price")
        return v


def _product_out(p: Product) -> dict:
    margin = round((p.price - p.cost) / p.price * 100, 1) if p.price else 0.0
    return {
        "on_sale": sale_active(p), "effective_price": effective_price(p),
        "sale_price": p.sale_price, "sale_ends": p.sale_ends.isoformat() if p.sale_ends else None,
        "id": p.id, "name": p.name, "sku": p.sku, "barcode": p.barcode, "brand": p.brand,
        "category": p.category, "subcategory": p.subcategory, "description": p.description,
        "unit_type": p.unit_type, "unit_size": p.unit_size,
        "price": p.price, "cost": p.cost, "mrp": p.mrp, "tax_rate": p.tax_rate,
        "stock": p.stock, "min_stock": p.min_stock, "max_stock": p.max_stock,
        "safety_stock": p.safety_stock, "reorder_level": p.reorder_level,
        "reorder_qty": p.reorder_qty, "daily_demand": p.daily_demand,
        "supplier_id": p.supplier_id, "supplier_cost": p.supplier_cost,
        "lead_time_days": p.lead_time_days, "moq": p.moq,
        "expiry_days": p.expiry_days, "storage_type": p.storage_type,
        "shelf_location": p.shelf_location, "is_demo": bool(p.is_demo),
        "margin_pct": margin,
        "days_of_stock": round(p.stock / max(p.daily_demand, 0.1), 1),
        "stock_status": "critical" if p.stock < p.daily_demand * 5
        else "low" if p.stock <= p.reorder_level
        else "overstock" if p.daily_demand > 0 and p.stock > p.daily_demand * 60
        else "healthy",
    }


@router.get("")
def list_products(
    search: str = "", category: str = "", status: str = "",
    sort: str = "name", order: str = "asc",
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    business: Business = Depends(get_current_business), db: Database = Depends(get_db),
):
    filt: dict = {"business_id": business.id}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        filt["$or"] = [{"name": rx}, {"sku": rx}, {"brand": rx}, {"category": rx}]
    if category:
        filt["category"] = category

    total = db.products.count_documents(filt)
    cur = db.products.find(filt)
    if sort in SORTABLE:
        cur = cur.sort(sort, DESCENDING if order == "desc" else ASCENDING)
    cur = cur.skip((page - 1) * page_size).limit(page_size)
    items = [_product_out(Product.from_doc(d)) for d in cur]
    if status:  # stock_status is computed, filter after serialization
        items = [i for i in items if i["stock_status"] == status]

    categories = sorted(c for c in db.products.distinct("category", {"business_id": business.id}) if c)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "categories": categories}


@router.get("/summary")
def products_summary(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    rows = find_models(db, Product, {"business_id": business.id})
    total_value = sum(p.stock * p.cost for p in rows)
    low = sum(1 for p in rows if 0 < p.stock <= p.reorder_level)
    out = sum(1 for p in rows if p.stock == 0)
    return {
        "count": len(rows), "inventory_value": round(total_value, 0),
        "low_stock": low, "out_of_stock": out,
        "demo_count": sum(1 for p in rows if p.is_demo),
        "avg_margin_pct": round(
            sum((p.price - p.cost) / p.price * 100 for p in rows if p.price) / max(len(rows), 1), 1),
    }


@router.get("/suppliers")
def list_suppliers(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    rows = find_models(db, Supplier, {"business_id": business.id})
    return {"items": [{"id": s.id, "name": s.name, "category": s.category,
                       "lead_time_days": s.lead_time_days, "reliability": s.reliability} for s in rows]}


@router.get("/stock-log")
def stock_log(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    """Recent manual stock adjustments (audit trail)."""
    rows = find_models(db, StockAdjustment, {"business_id": business.id},
                       sort=[("created_at", -1)], limit=25)
    return {"items": [{"id": a.id, "product_name": a.product_name, "delta": a.delta,
                       "reason": a.reason, "note": a.note, "stock_after": a.stock_after,
                       "created_at": a.created_at.isoformat()} for a in rows]}


class StockAdjustIn(BaseModel):
    delta: int  # +units received / -units removed
    reason: str = "correction"  # delivery | damaged | expired | theft | correction
    note: str = ""


@router.post("/{product_id}/stock")
def adjust_stock(product_id: str, body: StockAdjustIn,
                 business: Business = Depends(get_current_business),
                 db: Database = Depends(get_db)):
    if body.delta == 0:
        raise HTTPException(status_code=400, detail="Adjustment cannot be zero")
    p = get_owned(db, Product, product_id, business.id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    new_stock = p.stock + body.delta
    if new_stock < 0:
        raise HTTPException(status_code=400,
                            detail=f"Cannot remove {-body.delta} units — only {p.stock} in stock")
    db.products.update_one({"_id": oid(p.id)}, {"$set": {"stock": new_stock}})
    reason = body.reason if body.reason in ("delivery", "damaged", "expired", "theft", "correction") else "correction"
    insert_model(db, StockAdjustment(
        business_id=business.id, product_id=p.id, product_name=p.name,
        delta=body.delta, reason=reason, note=body.note.strip(), stock_after=new_stock))
    return _product_out(p.model_copy(update={"stock": new_stock}))


class SaleIn(BaseModel):
    sale_price: float = Field(gt=0)
    sale_ends: str | None = None  # ISO date; empty = until removed


@router.put("/{product_id}/sale")
def set_sale(product_id: str, body: SaleIn,
             business: Business = Depends(get_current_business),
             db: Database = Depends(get_db)):
    p = get_owned(db, Product, product_id, business.id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    ends = None
    if body.sale_ends:
        try:
            ends = date.fromisoformat(body.sale_ends)
        except ValueError:
            raise HTTPException(status_code=400, detail="sale_ends must be YYYY-MM-DD")
        if ends < date.today():
            raise HTTPException(status_code=400, detail="Sale end date is already in the past")
    db.products.update_one({"_id": oid(p.id)}, {"$set": {
        "sale_price": round(body.sale_price, 2),
        "sale_ends": to_dt(ends) if ends else None}})
    return _product_out(p.model_copy(update={"sale_price": round(body.sale_price, 2), "sale_ends": ends}))


@router.delete("/{product_id}/sale")
def clear_sale(product_id: str, business: Business = Depends(get_current_business),
               db: Database = Depends(get_db)):
    p = get_owned(db, Product, product_id, business.id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    db.products.update_one({"_id": oid(p.id)}, {"$set": {"sale_price": None, "sale_ends": None}})
    return _product_out(p.model_copy(update={"sale_price": None, "sale_ends": None}))


@router.get("/{product_id}")
def get_product(product_id: str, business: Business = Depends(get_current_business),
                db: Database = Depends(get_db)):
    p = get_owned(db, Product, product_id, business.id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_out(p)


@router.post("")
def create_product(body: ProductIn, business: Business = Depends(get_current_business),
                   db: Database = Depends(get_db)):
    if body.supplier_id is not None:
        sup = get_owned(db, Supplier, body.supplier_id, business.id)
        if not sup:
            raise HTTPException(status_code=400, detail="Unknown supplier")
    if body.sku:
        dup = db.products.find_one({"business_id": business.id, "sku": body.sku})
        if dup:
            raise HTTPException(status_code=400, detail=f"SKU '{body.sku}' already exists")
    p = Product(business_id=business.id, is_demo=0, **body.model_dump())
    if not p.sku:
        p.sku = f"SKU-{business.id[-4:].upper()}-{next_seq(db, f'sku:{business.id}'):04d}"
    insert_model(db, p)
    if business.data_source == "demo":
        db.businesses.update_one({"_id": oid(business.id)}, {"$set": {"data_source": "mixed"}})
    return _product_out(p)


@router.put("/{product_id}")
def update_product(product_id: str, body: ProductIn,
                   business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    p = get_owned(db, Product, product_id, business.id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    db.products.update_one({"_id": oid(product_id)}, {"$set": body.model_dump()})
    p = p.model_copy(update=body.model_dump())
    return _product_out(p)


@router.delete("/{product_id}")
def delete_product(product_id: str, business: Business = Depends(get_current_business),
                   db: Database = Depends(get_db)):
    p = get_owned(db, Product, product_id, business.id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    db.product_sales.delete_many({"product_id": p.id})
    db.products.delete_one({"_id": oid(p.id)})
    return {"ok": True}
