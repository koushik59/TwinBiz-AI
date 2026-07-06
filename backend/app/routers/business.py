from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, Employee, Product, Supplier, User
from ..security import get_current_business, get_current_user
from ..seed import seed_business

router = APIRouter(prefix="/api/business", tags=["business"])


class BusinessIn(BaseModel):
    name: str
    business_type: str = "Supermarket"
    location: str = ""
    employees_count: int = 5
    monthly_revenue: float = 500000
    monthly_expenses: float = 380000
    customer_count: int = 1200
    working_hours: str = "9:00-21:00"


class ProductIn(BaseModel):
    name: str
    category: str = "General"
    price: float
    cost: float
    stock: int = 50
    reorder_level: int = 15
    daily_demand: float = 5


def _business_out(b: Business) -> dict:
    return {
        "id": b.id, "name": b.name, "business_type": b.business_type, "location": b.location,
        "employees_count": b.employees_count, "monthly_revenue": b.monthly_revenue,
        "monthly_expenses": b.monthly_expenses, "customer_count": b.customer_count,
        "working_hours": b.working_hours, "currency": b.currency,
    }


@router.post("")
def create_business(body: BusinessIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(Business).filter(Business.owner_id == user.id).count() >= 3:
        raise HTTPException(status_code=400, detail="Business limit reached")
    business = Business(owner_id=user.id, **body.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)
    seed_business(db, business)  # generate 365 days of twin history instantly
    return _business_out(business)


@router.get("")
def get_business(business: Business = Depends(get_current_business)):
    return _business_out(business)


@router.put("")
def update_business(body: BusinessIn, business: Business = Depends(get_current_business),
                    db: Session = Depends(get_db)):
    for k, v in body.model_dump().items():
        setattr(business, k, v)
    db.commit()
    return _business_out(business)


@router.get("/twin")
def twin_snapshot(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    """Full digital-twin snapshot: layout entities with live per-entity metrics."""
    products = db.query(Product).filter(Product.business_id == business.id).all()
    employees = db.query(Employee).filter(Employee.business_id == business.id).all()
    suppliers = db.query(Supplier).filter(Supplier.business_id == business.id).all()
    return {
        "business": _business_out(business),
        "products": [
            {
                "id": p.id, "name": p.name, "category": p.category, "price": p.price, "cost": p.cost,
                "stock": p.stock, "reorder_level": p.reorder_level, "daily_demand": p.daily_demand,
                "margin_pct": round((p.price - p.cost) / p.price * 100, 1) if p.price else 0,
                "days_of_stock": round(p.stock / max(p.daily_demand, 0.1), 1),
                "stock_value": round(p.stock * p.cost, 0),
                "status": "critical" if p.stock < p.daily_demand * 5
                else "low" if p.stock <= p.reorder_level
                else "overstock" if p.daily_demand > 0 and p.stock > p.daily_demand * 60
                else "healthy",
            }
            for p in products
        ],
        "employees": [
            {"id": e.id, "name": e.name, "role": e.role, "salary": e.salary,
             "department": e.department, "performance": e.performance}
            for e in employees
        ],
        "suppliers": [
            {"id": s.id, "name": s.name, "category": s.category, "reliability": s.reliability,
             "lead_time_days": s.lead_time_days, "cost_index": s.cost_index}
            for s in suppliers
        ],
    }


@router.post("/products")
def add_product(body: ProductIn, business: Business = Depends(get_current_business),
                db: Session = Depends(get_db)):
    p = Product(business_id=business.id, **body.model_dump())
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.put("/products/{product_id}")
def update_product(product_id: int, body: ProductIn,
                   business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or p.business_id != business.id:
        raise HTTPException(status_code=404, detail="Product not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/products/{product_id}")
def delete_product(product_id: int, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or p.business_id != business.id:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(p)
    db.commit()
    return {"ok": True}
