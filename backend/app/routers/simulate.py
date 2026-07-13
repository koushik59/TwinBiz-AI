import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import func

from ..database import get_db
from ..models import Business, DailyMetric, Product, ProductSale, Scenario
from ..security import get_current_business
from ..services.forecasting import forecast_series, restock_predictions
from ..services.simulation import (MODEL_VERSION, PRICE_ELASTICITY, WHAT_IF_PRESETS,
                                   Baseline, Levers, product_price_simulation, simulate)

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


def _velocity(db: Session, business_id: int, product: Product) -> tuple[float, int]:
    """Real units/day for a product from its sales history (falls back to configured demand)."""
    since = date.today() - timedelta(days=30)
    row = (
        db.query(func.sum(ProductSale.units), func.count(func.distinct(ProductSale.day)))
        .filter(ProductSale.business_id == business_id, ProductSale.product_id == product.id,
                ProductSale.day >= since)
        .first()
    )
    total_units, days_with_sales = (row or (None, 0))
    history_days = (
        db.query(func.count(func.distinct(ProductSale.day)))
        .filter(ProductSale.business_id == business_id, ProductSale.product_id == product.id)
        .scalar() or 0
    )
    if total_units and days_with_sales:
        return total_units / 30.0, int(history_days)
    return max(product.daily_demand, 0.1), 0


class ProductPriceIn(BaseModel):
    product_id: int
    new_price: float

    @property
    def valid(self) -> bool:
        return self.new_price > 0


@router.post("/product-price")
def simulate_product_price(body: ProductPriceIn, business: Business = Depends(get_current_business),
                           db: Session = Depends(get_db)):
    """Product-level price what-if: e.g. raise Amul Milk from ₹28 to ₹30."""
    if body.new_price <= 0:
        raise HTTPException(status_code=400, detail="New price must be above 0")
    p = db.get(Product, body.product_id)
    if not p or p.business_id != business.id:
        raise HTTPException(status_code=404, detail="Product not found")
    units_per_day, history_days = _velocity(db, business.id, p)
    return product_price_simulation(
        name=p.name, category=p.category, current_price=p.price, cost=p.cost,
        new_price=body.new_price, units_per_day=units_per_day, stock=p.stock,
        lead_time_days=p.lead_time_days or 3, history_days=history_days,
    )


@router.get("/products")
def simulatable_products(business: Business = Depends(get_current_business),
                         db: Session = Depends(get_db)):
    """Product list for the simulator's product-price mode."""
    rows = db.query(Product).filter(Product.business_id == business.id).order_by(Product.name).all()
    return {"items": [{"id": p.id, "name": p.name, "category": p.category,
                       "price": p.price, "cost": p.cost, "stock": p.stock} for p in rows]}


@router.post("/run")
def run_simulation(body: LeversIn, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    base = _baseline(db, business)
    result = simulate(base, Levers(**body.model_dump()))
    current = simulate(base, Levers())  # untouched baseline for comparison
    btype = base.business_type if base.business_type in PRICE_ELASTICITY else "Retail"
    return {
        "current": current, "simulated": result, "levers": body.model_dump(),
        "how": {
            "model_version": MODEL_VERSION,
            "baseline_window": "last 30 days of twin history",
            "assumptions": [
                f"Business-level price elasticity {PRICE_ELASTICITY[btype]} for {btype}",
                "Marketing follows a diminishing-returns (tanh) response curve",
                "Staffing changes shift service capacity and satisfaction, ~₹18,000/month per employee",
                "COGS assumed at 55% of expenses when itemized costs are unavailable",
            ],
            "label": "Predicted (not guaranteed)",
        },
    }


WHAT_IF_LABELS = {
    "hire_1_cashier": "Hire one extra cashier",
    "festival_offer_10": "Launch 10% festival offer",
    "marketing_up_20": "Increase marketing by 20%",
    "stock_up_15": "Increase fast-moving stock by 15%",
    "extend_hours_2": "Extend store hours by 2",
    "cheaper_supplier": "Switch to cheaper supplier",
    "cut_opex_10": "Reduce operating expenses by 10%",
    "increase_price_10": "Increase all prices 10%",
    "decrease_price_10": "Decrease all prices 10%",
    "double_marketing": "Double marketing budget",
}


@router.get("/what-if")
def what_if(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    """Run every preset action and return ranked outcomes."""
    base = _baseline(db, business)
    current = simulate(base, Levers())
    results = []

    # product-level headline presets: milk price ± ₹2 (§13)
    milk = (
        db.query(Product)
        .filter(Product.business_id == business.id, Product.name.ilike("%milk%"))
        .order_by(Product.daily_demand.desc())
        .first()
    )
    if milk and milk.price > 2:
        units_per_day, history_days = _velocity(db, business.id, milk)
        for delta, key in ((2, "milk_price_up_2"), (-2, "milk_price_down_2")):
            sim = product_price_simulation(
                name=milk.name, category=milk.category, current_price=milk.price,
                cost=milk.cost, new_price=milk.price + delta, units_per_day=units_per_day,
                stock=milk.stock, lead_time_days=milk.lead_time_days or 3,
                history_days=history_days,
            )
            results.append({
                "key": key,
                "label": f"{'Increase' if delta > 0 else 'Decrease'} {milk.name} price by ₹2",
                "kind": "product_price",
                "result": sim,
                "profit_delta": sim["delta"]["gross_profit"],
            })

    for key, levers in WHAT_IF_PRESETS.items():
        sim = simulate(base, levers)
        results.append({
            "key": key, "label": WHAT_IF_LABELS[key], "kind": "business",
            "result": sim, "levers": levers.__dict__,
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

    # multi-criteria highlights (§14): never just "highest revenue"
    def _pick(metric, reverse=True):
        ranked = sorted(items, key=lambda s: s["results"].get(metric, 0), reverse=reverse)
        return ranked[0]["id"] if ranked else None

    def _balanced(s):
        r = s["results"]
        # profit normalized against the current baseline, penalized by risk
        profit_gain = (r.get("profit", 0) - current["profit"]) / max(abs(current["profit"]), 1)
        return profit_gain * 100 - r.get("risk_score", 50) * 0.4 + r.get("satisfaction", 50) * 0.2

    recommended = max(items, key=_balanced, default=None)
    return {
        "current": current, "scenarios": items,
        "best_id": best["id"] if best else None,
        "highlights": {
            "best_profit": _pick("profit"),
            "best_growth": _pick("customers"),
            "lowest_risk": _pick("risk_score", reverse=False),
            "ai_recommended": recommended["id"] if recommended else None,
        },
    }


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
