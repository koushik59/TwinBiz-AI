"""Product Launch Lab API (§45): CRUD + simulations for product experiments."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, ProductExperiment, ProductExperimentScenario
from ..security import get_current_business
from ..services import launch_lab
from ..services.gemini import ask_gemini

router = APIRouter(prefix="/api/product-experiments", tags=["product-experiments"])


class ExperimentIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    brand: str = ""
    category: str = "General"
    subcategory: str = ""
    description: str = ""
    unit_type: str = "pcs"
    unit_size: str = ""

    supplier_cost: float = Field(gt=0)
    transport_cost: float = Field(default=0, ge=0)
    storage_cost: float = Field(default=0, ge=0)
    handling_cost: float = Field(default=0, ge=0)
    other_variable_cost: float = Field(default=0, ge=0)
    wastage_percent: float = Field(default=0, ge=0, le=60)
    tax_rate: float = Field(default=0, ge=0, le=100)

    min_price: float = Field(gt=0)
    max_price: float = Field(gt=0)
    price_step: float = Field(gt=0)
    planned_price: float = Field(gt=0)

    discount_percent: float = Field(default=0, ge=0, le=100)
    initial_stock: int = Field(default=100, ge=0)
    safety_stock: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    supplier_lead_time: int = Field(default=3, ge=0, le=60)
    marketing_budget: float = Field(default=0, ge=0)
    launch_date: str = ""
    target_segment: str = "All Customers"
    shelf_placement: str = "Middle Shelf"
    competitor_price: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_ranges(self):
        if self.max_price < self.min_price:
            raise ValueError("Maximum test price must be ≥ minimum test price")
        if not (self.min_price <= self.planned_price <= self.max_price):
            raise ValueError("Planned launch price must lie within the test price range")
        if (self.max_price - self.min_price) / self.price_step > 60:
            raise ValueError("Price step too small — that would create over 60 price points")
        return self


class OptimizeIn(BaseModel):
    min_price: float | None = Field(default=None, gt=0)
    max_price: float | None = Field(default=None, gt=0)
    max_discount: float = Field(default=20, ge=0, le=100)
    max_stock: int | None = Field(default=None, gt=0)
    max_marketing: float | None = Field(default=None, ge=0)
    min_margin_pct: float = Field(default=5, ge=0, le=90)


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    price: float = Field(gt=0)
    discount: float = Field(default=0, ge=0, le=100)
    stock: int = Field(default=100, gt=0)
    marketing_budget: float = Field(default=0, ge=0)


class SweepIn(BaseModel):
    base_price: float | None = Field(default=None, gt=0)


def _exp_out(e: ProductExperiment) -> dict:
    return {
        "id": e.id, "product_name": e.product_name, "brand": e.brand, "category": e.category,
        "subcategory": e.subcategory, "description": e.description,
        "unit_type": e.unit_type, "unit_size": e.unit_size,
        "supplier_cost": e.supplier_cost, "transport_cost": e.transport_cost,
        "storage_cost": e.storage_cost, "handling_cost": e.handling_cost,
        "other_variable_cost": e.other_variable_cost, "wastage_percent": e.wastage_percent,
        "tax_rate": e.tax_rate, "landed_cost": launch_lab.landed_cost(e),
        "min_price": e.min_price, "max_price": e.max_price, "price_step": e.price_step,
        "planned_price": e.planned_price, "discount_percent": e.discount_percent,
        "initial_stock": e.initial_stock, "safety_stock": e.safety_stock,
        "reorder_point": e.reorder_point, "supplier_lead_time": e.supplier_lead_time,
        "marketing_budget": e.marketing_budget, "launch_date": e.launch_date,
        "target_segment": e.target_segment, "shelf_placement": e.shelf_placement,
        "competitor_price": e.competitor_price, "status": e.status,
        "created_at": e.created_at.isoformat(),
    }


def _get_exp(db: Session, business: Business, exp_id: int) -> ProductExperiment:
    e = db.get(ProductExperiment, exp_id)
    if not e or e.business_id != business.id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return e


@router.get("/options")
def options():
    return {
        "segments": list(launch_lab.TARGET_SEGMENTS),
        "placements": list(launch_lab.SHELF_PLACEMENT),
    }


@router.get("/demo-preset")
def demo_preset():
    """One-click 'Launch New Product Demo' prefill (§49)."""
    return {
        "product_name": "Amul Protein Lassi 200ml", "brand": "Amul", "category": "Dairy",
        "subcategory": "Beverages", "unit_type": "pcs", "unit_size": "200ml",
        "description": "High-protein lassi targeted at fitness-conscious shoppers",
        "supplier_cost": 25, "transport_cost": 1, "storage_cost": 0.5, "handling_cost": 0.5,
        "other_variable_cost": 0, "wastage_percent": 3, "tax_rate": 5,
        "min_price": 30, "max_price": 50, "price_step": 2, "planned_price": 40,
        "discount_percent": 10, "initial_stock": 200, "safety_stock": 30, "reorder_point": 70,
        "supplier_lead_time": 3, "marketing_budget": 5000, "launch_date": "",
        "target_segment": "Young Adults", "shelf_placement": "Refrigerated Section",
        "competitor_price": 45,
    }


@router.post("")
def create_experiment(body: ExperimentIn, business: Business = Depends(get_current_business),
                      db: Session = Depends(get_db)):
    e = ProductExperiment(business_id=business.id, **body.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return _exp_out(e)


@router.get("")
def list_experiments(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    rows = (db.query(ProductExperiment).filter(ProductExperiment.business_id == business.id)
            .order_by(ProductExperiment.created_at.desc()).all())
    return {"items": [_exp_out(e) for e in rows]}


@router.get("/{exp_id}")
def get_experiment(exp_id: int, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    return _exp_out(_get_exp(db, business, exp_id))


@router.put("/{exp_id}")
def update_experiment(exp_id: int, body: ExperimentIn,
                      business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    db.commit()
    return _exp_out(e)


@router.delete("/{exp_id}")
def delete_experiment(exp_id: int, business: Business = Depends(get_current_business),
                      db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.post("/{exp_id}/price-sweep")
def run_price_sweep(exp_id: int, business: Business = Depends(get_current_business),
                    db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    result = launch_lab.price_sweep(db, business, e)
    e.status = "simulated"
    db.commit()
    return result


@router.post("/{exp_id}/discount-sweep")
def run_discount_sweep(exp_id: int, body: SweepIn | None = None,
                       business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    return launch_lab.discount_sweep(db, business, e, base_price=body.base_price if body else None)


@router.post("/{exp_id}/inventory-sweep")
def run_inventory_sweep(exp_id: int, body: SweepIn | None = None,
                        business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    return launch_lab.inventory_sweep(db, business, e, price=body.base_price if body else None)


@router.post("/{exp_id}/optimize")
def run_optimize(exp_id: int, body: OptimizeIn,
                 business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    return launch_lab.optimize(db, business, e, **body.model_dump())


@router.post("/{exp_id}/analysis")
def run_analysis(exp_id: int, business: Business = Depends(get_current_business),
                 db: Session = Depends(get_db)):
    """Full launch dossier at the planned configuration: point prediction,
    cannibalization, timing, break-even and before/after view."""
    e = _get_exp(db, business, exp_id)
    point = launch_lab.simulate_point(db, business, e, price=e.planned_price,
                                      discount=e.discount_percent)
    return {
        "point": point,
        "cannibalization": launch_lab.cannibalization(db, business, e, point),
        "timing": launch_lab.launch_timing(db, business, e),
        "before_after": launch_lab.before_after(db, business, e, point),
        "assumptions": launch_lab._assumptions(e, launch_lab.category_anchor(db, business, e)),
        "model_version": launch_lab.MODEL_VERSION,
    }


@router.post("/{exp_id}/scenarios")
def save_scenario(exp_id: int, body: ScenarioIn,
                  business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    point = launch_lab.simulate_point(db, business, e, price=body.price,
                                      discount=body.discount, stock=body.stock,
                                      marketing=body.marketing_budget)
    sc = ProductExperimentScenario(
        experiment_id=e.id, name=body.name, price=body.price, discount=body.discount,
        stock=body.stock, marketing_budget=body.marketing_budget,
        results_json=json.dumps(point),
        assumptions_json=json.dumps(launch_lab._assumptions(
            e, launch_lab.category_anchor(db, business, e))),
    )
    db.add(sc)
    db.commit()
    return {"id": sc.id, "name": sc.name, "results": point}


@router.get("/{exp_id}/scenarios")
def list_scenarios(exp_id: int, business: Business = Depends(get_current_business),
                   db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    rows = (db.query(ProductExperimentScenario)
            .filter(ProductExperimentScenario.experiment_id == e.id)
            .order_by(ProductExperimentScenario.created_at.desc()).limit(6).all())
    items = [{"id": s.id, "name": s.name, "price": s.price, "discount": s.discount,
              "stock": s.stock, "marketing_budget": s.marketing_budget,
              "results": json.loads(s.results_json), "created_at": s.created_at.isoformat()}
             for s in rows]

    highlights = {}
    if items:
        highlights = {
            "best_profit": max(items, key=lambda s: s["results"]["net_contribution"])["id"],
            "best_growth": max(items, key=lambda s: s["results"]["predicted_units_sold"])["id"],
            "lowest_risk": min(items, key=lambda s: s["results"]["risk_score"])["id"],
        }
        best_np = max(abs(s["results"]["net_contribution"]) for s in items) or 1
        highlights["ai_recommended"] = max(items, key=lambda s: (
            s["results"]["net_contribution"] / best_np * 0.45
            + s["results"]["customer_acceptance_pct"] / 100 * 0.25
            - s["results"]["risk_score"] / 100 * 0.30
        ))["id"]
    return {"items": items, "highlights": highlights}


@router.delete("/{exp_id}/scenarios/{scenario_id}")
def delete_scenario(exp_id: int, scenario_id: int,
                    business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    e = _get_exp(db, business, exp_id)
    sc = db.get(ProductExperimentScenario, scenario_id)
    if not sc or sc.experiment_id != e.id:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(sc)
    db.commit()
    return {"ok": True}


@router.post("/{exp_id}/advisor")
async def launch_advisor(exp_id: int, business: Business = Depends(get_current_business),
                         db: Session = Depends(get_db)):
    """'Should I launch this product?' — deterministic verdict from the twin engine,
    optionally narrated by Gemini. All numbers come from the simulation (§41)."""
    e = _get_exp(db, business, exp_id)
    sweep = launch_lab.price_sweep(db, business, e)
    planned = launch_lab.simulate_point(db, business, e, price=e.planned_price,
                                        discount=e.discount_percent)
    best = sweep["recommendations"]["balanced"]
    cann = launch_lab.cannibalization(db, business, e, planned)

    # deterministic decision rules
    if planned["margin_pct"] <= 0:
        decision = "HIGH RISK"
        reason = (f"At the planned ₹{e.planned_price} price the landed cost of "
                  f"₹{planned['landed_cost']} leaves a negative margin.")
    elif planned["risk_score"] >= 70:
        decision = "HIGH RISK"
        reason = f"Overall launch risk is {planned['risk_score']}/100 ({planned['risk_level']})."
    elif planned["risk_score"] >= 50 or planned["confidence_pct"] < 45:
        decision = "WAIT"
        reason = ("Risk is elevated and comparable history is thin — collect more category "
                  "sales data or test a smaller initial stock.")
    elif abs(best["price"] - e.planned_price) > e.price_step or planned["margin_pct"] < 12:
        decision = "CONDITIONAL YES"
        reason = (f"Demand looks healthy, but ₹{e.planned_price} is not the best configuration — "
                  f"the balanced optimum is ₹{best['price']}.")
    else:
        decision = "YES"
        reason = (f"Planned price ₹{e.planned_price} is near the balanced optimum ₹{best['price']} "
                  f"with a {planned['margin_pct']}% margin and {planned['risk_level'].lower()} risk.")

    verdict = {
        "decision": decision,
        "reason": reason,
        "recommendation": (
            f"Launch around ₹{best['price']} with ~{launch_lab.inventory_sweep(db, business, e)['recommended_stock']} "
            f"units of initial stock. Predicted: {best['predicted_units_sold']:.0f} units and "
            f"₹{best['predicted_revenue']:,.0f} revenue in month 1, "
            f"₹{best['predicted_gross_profit']:,.0f}/month recurring gross profit "
            f"(₹{best['net_3_months']:,.0f} net over 3 months after the one-time marketing spend)."),
        "main_risk": (
            f"Stockout within {planned['days_of_cover']:.0f} days of cover"
            if planned["stockout_risk"] != "low"
            else f"Cannibalization: ~{cann['estimated_existing_loss_units']:.0f} units/month may shift from "
                 f"{cann['affected_products'][0]['product'] if cann['affected_products'] else 'existing products'}"
            if cann["risk"] != "low" else "Demand may build slower than the category anchor suggests"),
        "suggested_action": (
            f"Set a reorder trigger near {max(e.reorder_point, int(planned['predicted_units_per_day'] * (e.supplier_lead_time + 2)))} units."),
        "planned_point": planned,
        "best_point": best,
        "cannibalization": cann,
        "confidence_pct": planned["confidence_pct"],
        "source": "twin-engine",
    }

    # let Gemini narrate the verdict (never invent numbers) when configured
    context = {
        "experiment": {"name": e.product_name, "category": e.category,
                       "planned_price": e.planned_price, "landed_cost": planned["landed_cost"]},
        "twin_engine_verdict": {k: v for k, v in verdict.items()
                                if k not in ("planned_point", "best_point")},
        "instruction": ("Explain this launch verdict to the owner in under 150 words. Use ONLY the "
                        "numbers provided above — do not invent any figures. Keep the same decision."),
    }
    try:
        narrated = await ask_gemini(
            f"Should I launch {e.product_name}? Explain the twin engine's verdict.", context)
        if narrated.get("source") == "gemini":
            verdict["narrative"] = narrated["answer"]
            verdict["source"] = "twin-engine + gemini"
    except Exception:
        pass
    return verdict
