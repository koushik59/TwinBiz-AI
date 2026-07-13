"""Real product management: full CRUD with search / filter / sort / pagination (§6)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, Product, ProductSale, Supplier
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
    supplier_id: int | None = None
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
    business: Business = Depends(get_current_business), db: Session = Depends(get_db),
):
    q = db.query(Product).filter(Product.business_id == business.id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Product.name.ilike(like), Product.sku.ilike(like),
                         Product.brand.ilike(like), Product.category.ilike(like)))
    if category:
        q = q.filter(Product.category == category)

    total = q.count()
    if sort in SORTABLE:
        col = getattr(Product, sort)
        q = q.order_by(desc(col) if order == "desc" else asc(col))
    items = [_product_out(p) for p in q.offset((page - 1) * page_size).limit(page_size).all()]
    if status:  # stock_status is computed, filter after serialization
        items = [i for i in items if i["stock_status"] == status]

    categories = [c for (c,) in db.query(Product.category).filter(
        Product.business_id == business.id).distinct().order_by(Product.category).all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "categories": categories}


@router.get("/summary")
def products_summary(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    rows = db.query(Product).filter(Product.business_id == business.id).all()
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
def list_suppliers(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    rows = db.query(Supplier).filter(Supplier.business_id == business.id).all()
    return {"items": [{"id": s.id, "name": s.name, "category": s.category,
                       "lead_time_days": s.lead_time_days, "reliability": s.reliability} for s in rows]}


@router.get("/{product_id}")
def get_product(product_id: int, business: Business = Depends(get_current_business),
                db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or p.business_id != business.id:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_out(p)


@router.post("")
def create_product(body: ProductIn, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    if body.supplier_id is not None:
        sup = db.get(Supplier, body.supplier_id)
        if not sup or sup.business_id != business.id:
            raise HTTPException(status_code=400, detail="Unknown supplier")
    if body.sku:
        dup = db.query(Product).filter(Product.business_id == business.id,
                                       Product.sku == body.sku).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"SKU '{body.sku}' already exists")
    p = Product(business_id=business.id, is_demo=0, **body.model_dump())
    if not p.sku:
        db.add(p)
        db.flush()
        p.sku = f"SKU-{business.id:03d}-{p.id:04d}"
    else:
        db.add(p)
    if business.data_source == "demo":
        business.data_source = "mixed"
    db.commit()
    return _product_out(p)


@router.put("/{product_id}")
def update_product(product_id: int, body: ProductIn,
                   business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or p.business_id != business.id:
        raise HTTPException(status_code=404, detail="Product not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return _product_out(p)


@router.delete("/{product_id}")
def delete_product(product_id: int, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or p.business_id != business.id:
        raise HTTPException(status_code=404, detail="Product not found")
    db.query(ProductSale).filter(ProductSale.product_id == p.id).delete()
    db.delete(p)
    db.commit()
    return {"ok": True}
