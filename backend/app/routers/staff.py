"""Staff management: full employee CRUD with payroll summary.

The business's employees_count is kept in sync with the actual roster, so the
Simulator's staffing baseline recalibrates automatically as the team changes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database

from ..database import get_db, oid
from ..models import Business, Employee, find_models, get_owned, insert_model
from ..security import get_current_business

router = APIRouter(prefix="/api/staff", tags=["staff"])

ROLES = ["Manager", "Cashier", "Sales Associate", "Stock Keeper", "Helper", "Staff"]
DEPARTMENTS = ["Management", "Operations", "Sales", "Warehouse"]


class EmployeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = "Staff"
    department: str = "Operations"
    salary: float = Field(default=18000, ge=0)
    performance: float = Field(default=0.8, ge=0, le=1)  # 0..1


def _employee_out(e: Employee) -> dict:
    return {"id": e.id, "name": e.name, "role": e.role, "department": e.department,
            "salary": e.salary, "performance": e.performance}


def _sync_headcount(db: Database, business: Business) -> int:
    """Keep business.employees_count = live roster size (simulator baseline)."""
    count = db.employees.count_documents({"business_id": business.id})
    db.businesses.update_one({"_id": oid(business.id)},
                             {"$set": {"employees_count": count}})
    business.employees_count = count
    return count


@router.get("")
def list_staff(business: Business = Depends(get_current_business),
               db: Database = Depends(get_db)):
    rows = find_models(db, Employee, {"business_id": business.id}, sort=[("name", 1)])
    payroll = sum(e.salary for e in rows)
    return {
        "items": [_employee_out(e) for e in rows],
        "options": {"roles": ROLES, "departments": DEPARTMENTS},
        "summary": {
            "headcount": len(rows),
            "monthly_payroll": round(payroll),
            "avg_salary": round(payroll / len(rows)) if rows else 0,
            "avg_performance_pct": round(sum(e.performance for e in rows) / len(rows) * 100) if rows else 0,
        },
    }


@router.post("")
def create_employee(body: EmployeeIn, business: Business = Depends(get_current_business),
                    db: Database = Depends(get_db)):
    e = insert_model(db, Employee(business_id=business.id, **body.model_dump()))
    _sync_headcount(db, business)
    return _employee_out(e)


@router.put("/{employee_id}")
def update_employee(employee_id: str, body: EmployeeIn,
                    business: Business = Depends(get_current_business),
                    db: Database = Depends(get_db)):
    e = get_owned(db, Employee, employee_id, business.id)
    if not e:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.employees.update_one({"_id": oid(e.id)}, {"$set": body.model_dump()})
    return _employee_out(e.model_copy(update=body.model_dump()))


@router.delete("/{employee_id}")
def delete_employee(employee_id: str, business: Business = Depends(get_current_business),
                    db: Database = Depends(get_db)):
    e = get_owned(db, Employee, employee_id, business.id)
    if not e:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.employees.delete_one({"_id": oid(e.id)})
    _sync_headcount(db, business)
    return {"ok": True}
