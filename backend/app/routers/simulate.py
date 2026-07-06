import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, DailyMetric, Product, Scenario
from ..security import get_current_business
from ..services.forecasting import forecast_series, restock_predictions
from ..services.simulation import WHAT_IF_PRESETS, Baseline, Levers, simulate

router = APIRouter(prefix="/api/simulate", tags=["simulate"])


class LeversIn(BaseModel):
    price_change_pct: float = 0
    marketing_change_pct: float = 0
    employee_delta: int = 0
    discount_pct: float = 0
    inventory_change_pct: float = 0
    hours_delta: float = 0
    supplier_cost_change_pct: float = 0
    opex_change_pct: float = 0


class ScenarioIn(BaseModel):
    name: str
    levers: LeversIn


def _baseline(db: Session, business: Business) -> Baseline:
    since = date.today() - timedelta(days=30)
    rows = (
        db.query(DailyMetric)
        .filter(DailyMetric.business_id == business.id, DailyMetric.day >= since)
        .all()
    )
    products = db.query(Product).filter(Product.business_id == business.id).all()
    inv_value = sum(p.stock * p.cost for p in products)
    if rows:
        return Baseline(
            monthly_revenue=sum(r.revenue for r in rows),
            monthly_expenses=sum(r.expenses for r in rows),
            monthly_customers=sum(r.customers for r in rows),
            employees=business.employees_count,
            inventory_value=inv_value or business.monthly_revenue * 0.4,
            business_type=business.business_type,
        )
    return Baseline(
        monthly_revenue=business.monthly_revenue, monthly_expenses=business.monthly_expenses,
        monthly_customers=business.customer_count, employees=business.employees_count,
        inventory_value=inv_value or business.monthly_revenue * 0.4,
        business_type=business.business_type,
    )


@router.post("/run")
def run_simulation(body: LeversIn, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    base = _baseline(db, business)
    result = simulate(base, Levers(**body.model_dump()))
    current = simulate(base, Levers())  # untouched baseline for comparison
    return {"current": current, "simulated": result, "levers": body.model_dump()}


@router.get("/what-if")
def what_if(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    """Run every preset action and return ranked outcomes."""
    base = _baseline(db, business)
    current = simulate(base, Levers())
    labels = {
        "increase_price_10": "Increase prices 10%", "decrease_price_10": "Decrease prices 10%",
        "hire_2_employees": "Hire 2 employees", "reduce_1_employee": "Reduce 1 employee",
        "festival_offer": "Launch festival offer", "double_marketing": "Double marketing budget",
        "reduce_inventory_20": "Reduce inventory 20%", "cheaper_supplier": "Switch to cheaper supplier",
        "extend_hours_2": "Extend hours by 2", "cut_opex_15": "Cut operating expenses 15%",
    }
    results = []
    for key, levers in WHAT_IF_PRESETS.items():
        sim = simulate(base, levers)
        results.append({
            "key": key, "label": labels[key], "result": sim,
            "profit_delta": sim["profit"] - current["profit"],
        })
    results.sort(key=lambda r: r["profit_delta"], reverse=True)
    return {"current": current, "actions": results}


@router.post("/scenarios")
def save_scenario(body: ScenarioIn, business: Business = Depends(get_current_business),
                  db: Session = Depends(get_db)):
    base = _baseline(db, business)
    result = simulate(base, Levers(**body.levers.model_dump()))
    sc = Scenario(business_id=business.id, name=body.name,
                  levers_json=json.dumps(body.levers.model_dump()), results_json=json.dumps(result))
    db.add(sc)
    db.commit()
    return {"id": sc.id, "name": sc.name, "levers": body.levers.model_dump(), "results": result}


@router.get("/scenarios")
def list_scenarios(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    base = _baseline(db, business)
    current = simulate(base, Levers())
    scenarios = (
        db.query(Scenario).filter(Scenario.business_id == business.id)
        .order_by(Scenario.created_at.desc()).limit(8).all()
    )
    items = [
        {"id": s.id, "name": s.name, "levers": json.loads(s.levers_json),
         "results": json.loads(s.results_json), "created_at": s.created_at.isoformat()}
        for s in scenarios
    ]
    best = max(items, key=lambda s: s["results"].get("profit", 0), default=None)
    return {"current": current, "scenarios": items, "best_id": best["id"] if best else None}


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: int, business: Business = Depends(get_current_business),
                    db: Session = Depends(get_db)):
    sc = db.get(Scenario, scenario_id)
    if not sc or sc.business_id != business.id:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(sc)
    db.commit()
    return {"ok": True}


@router.get("/forecast")
def forecast(metric: str = "revenue", horizon: int = 30,
             business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    if metric not in {"revenue", "customers", "orders", "expenses"}:
        raise HTTPException(status_code=400, detail="Unknown metric")
    horizon = max(7, min(horizon, 90))
    since = date.today() - timedelta(days=180)
    rows = (
        db.query(DailyMetric)
        .filter(DailyMetric.business_id == business.id, DailyMetric.day >= since)
        .order_by(DailyMetric.day)
        .all()
    )
    history = [(r.day, float(getattr(r, metric))) for r in rows]
    result = forecast_series(history, horizon)
    result["history"] = [{"day": d.isoformat(), "value": v} for d, v in history[-60:]]
    fc = result["forecast"]
    result["summary"] = {
        "next_day": fc[0]["value"] if fc else 0,
        "next_week": round(sum(p["value"] for p in fc[:7]), 0),
        "next_month": round(sum(p["value"] for p in fc[:30]), 0),
    }
    return result


@router.get("/restock")
def restock(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.business_id == business.id).all()
    return {"items": restock_predictions(products)}
