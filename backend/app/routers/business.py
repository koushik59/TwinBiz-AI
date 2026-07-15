from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.database import Database

from ..database import get_db, oid
from ..models import Business, Employee, Product, Supplier, User, find_models, insert_model
from ..security import get_current_business, get_current_user
from ..seed import seed_business
from ..services.insights import twin_status

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


class BusinessCreate(BusinessIn):
    # "demo" seeds a labeled 365-day synthetic twin; "manual"/"upload" start empty
    start_mode: str = "demo"


def _business_out(b: Business) -> dict:
    return {
        "id": b.id, "name": b.name, "business_type": b.business_type, "location": b.location,
        "employees_count": b.employees_count, "monthly_revenue": b.monthly_revenue,
        "monthly_expenses": b.monthly_expenses, "customer_count": b.customer_count,
        "working_hours": b.working_hours, "currency": b.currency,
        "data_source": b.data_source,
    }


@router.post("")
def create_business(body: BusinessCreate, user: User = Depends(get_current_user), db: Database = Depends(get_db)):
    if db.businesses.count_documents({"owner_id": user.id}) >= 3:
        raise HTTPException(status_code=400, detail="Business limit reached")
    business = Business(owner_id=user.id, **body.model_dump(exclude={"start_mode"}))
    business.data_source = "demo" if body.start_mode == "demo" else "real"
    insert_model(db, business)
    if body.start_mode == "demo":
        seed_business(db, business)  # 365 days of clearly-labeled synthetic twin history
    return _business_out(business)


@router.get("")
def get_business(business: Business = Depends(get_current_business)):
    return _business_out(business)


@router.put("")
def update_business(body: BusinessIn, business: Business = Depends(get_current_business),
                    db: Database = Depends(get_db)):
    db.businesses.update_one({"_id": oid(business.id)}, {"$set": body.model_dump()})
    business = business.model_copy(update=body.model_dump())
    return _business_out(business)


@router.get("/twin")
def twin_snapshot(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    """Full digital-twin snapshot: layout entities with live per-entity metrics."""
    products = find_models(db, Product, {"business_id": business.id})
    employees = find_models(db, Employee, {"business_id": business.id})
    suppliers = find_models(db, Supplier, {"business_id": business.id})
    return {
        "business": _business_out(business),
        "twin_status": twin_status(db, business),
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
