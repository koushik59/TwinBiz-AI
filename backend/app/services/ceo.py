"""AI CEO Mode: converts the twin's live analysis into concrete proposed
decisions with an approve/reject inbox.

Honest by design: approving a price decision actually updates the product;
approving a restock records the order for the owner to place (the twin cannot
receive goods on its own). Every proposal carries a simulated impact.
"""

import json
from datetime import date, timedelta, timezone
from datetime import datetime as dt

from pymongo.database import Database

from ..database import oid
from ..models import Business, Decision, find_models, insert_model, utcnow
from .forecasting import restock_predictions
from .insights import _business_products, _recent_metrics, detect_risks
from .simulation import (CATEGORY_ELASTICITY, Baseline, Levers,
                         product_price_simulation, simulate)

REJECT_COOLDOWN_DAYS = 14


def _baseline(db: Database, business: Business) -> Baseline:
    rows = _recent_metrics(db, business.id, 30)
    products = _business_products(db, business.id)
    inv = sum(p.stock * p.cost for p in products)
    if rows:
        return Baseline(monthly_revenue=sum(r.revenue for r in rows),
                        monthly_expenses=sum(r.expenses for r in rows),
                        monthly_customers=sum(r.customers for r in rows),
                        employees=business.employees_count,
                        inventory_value=inv or business.monthly_revenue * 0.4,
                        business_type=business.business_type)
    return Baseline(monthly_revenue=business.monthly_revenue,
                    monthly_expenses=business.monthly_expenses,
                    monthly_customers=business.customer_count,
                    employees=business.employees_count,
                    inventory_value=inv or business.monthly_revenue * 0.4,
                    business_type=business.business_type)


def _blocked_keys(db: Database, business_id: str) -> set[str]:
    """Keys we must not re-propose: anything pending/approved, or recently rejected."""
    cutoff = utcnow() - timedelta(days=REJECT_COOLDOWN_DAYS)
    blocked = set()
    for d in db.decisions.find({"business_id": business_id}, {"key": 1, "status": 1, "decided_at": 1}):
        if d["status"] in ("pending", "approved"):
            blocked.add(d["key"])
        elif d["status"] == "rejected":
            decided = d.get("decided_at")
            if decided and decided.replace(tzinfo=timezone.utc) >= cutoff:
                blocked.add(d["key"])
    return blocked


def generate_decisions(db: Database, business: Business) -> int:
    """Scan the twin and file new proposed decisions. Returns how many were created."""
    products = _business_products(db, business.id)
    blocked = _blocked_keys(db, business.id)
    created = 0

    def propose(d: Decision):
        nonlocal created
        if d.key in blocked:
            return
        insert_model(db, d)
        blocked.add(d.key)
        created += 1

    # 1. Restock the most urgent products
    for r in restock_predictions(products):
        if r["status"] not in ("critical", "low") or r["suggested_order"] <= 0:
            continue
        product = next((p for p in products if p.id == r["product_id"]), None)
        if not product:
            continue
        lost = r["daily_demand"] * product.price
        propose(Decision(
            business_id=business.id, key=f"restock:{r['product_id']}", kind="restock",
            title=f"Order {r['suggested_order']} units of {r['name']}",
            detail=(f"Stock covers only {r['days_until_stockout']:.0f} days at "
                    f"{r['daily_demand']}/day. Restock by {r['restock_by']} to avoid losing "
                    f"≈₹{lost:,.0f}/day in sales."),
            expected_impact=f"Prevents ≈₹{lost * 7:,.0f}/week of lost sales",
            impact_inr=round(lost * 30),
            action_type="log_order",
            action_json=json.dumps({"product_id": r["product_id"], "qty": r["suggested_order"]}),
        ))
        if sum(1 for k in blocked if k.startswith("restock:")) >= 4:
            break

    # 2. Price headroom on high-velocity, low-elasticity products
    inelastic = [p for p in products
                 if abs(CATEGORY_ELASTICITY.get(p.category, -1.5)) < 1.0 and p.price > 10]
    for p in sorted(inelastic, key=lambda x: -(x.daily_demand * x.price))[:2]:
        new_price = round(p.price * 1.04)
        if new_price <= p.price:
            continue
        sim = product_price_simulation(
            name=p.name, category=p.category, current_price=p.price, cost=p.cost,
            new_price=new_price, units_per_day=max(p.daily_demand, 0.1), stock=p.stock,
            lead_time_days=p.lead_time_days or 3)
        gain = sim["delta"]["gross_profit"]
        if gain <= 0:
            continue
        propose(Decision(
            business_id=business.id, key=f"price:{p.id}:{new_price}", kind="price",
            title=f"Raise {p.name} from ₹{p.price:g} to ₹{new_price:g}",
            detail=(f"{p.category} demand is price-tolerant (elasticity "
                    f"{CATEGORY_ELASTICITY.get(p.category, -1.5)}). Simulated demand change "
                    f"{sim['delta']['demand_pct']:+.1f}%, gross profit {gain:+,.0f}₹/month."),
            expected_impact=f"≈₹{gain:,.0f}/month extra gross profit",
            impact_inr=round(gain),
            action_type="update_price",
            action_json=json.dumps({"product_id": p.id, "new_price": new_price}),
        ))

    # 3. Clearance on overstock
    over = [p for p in products if p.daily_demand > 0 and p.stock > p.daily_demand * 60]
    if over:
        capital = sum(p.stock * p.cost for p in over)
        names = ", ".join(p.name for p in sorted(over, key=lambda p: -p.stock * p.cost)[:3])
        propose(Decision(
            business_id=business.id, key=f"clearance:{date.today().strftime('%Y-%m')}",
            kind="clearance",
            title=f"Run a 12% clearance on {len(over)} slow mover(s)",
            detail=f"₹{capital:,.0f} is locked in stock exceeding 60 days of demand ({names}…). "
                   f"A short clearance frees working capital for fast movers.",
            expected_impact=f"Frees ≈₹{capital * 0.6:,.0f} of working capital",
            impact_inr=round(capital * 0.6),
            action_type="advice", action_json="{}",
        ))

    # 4. Marketing boost when sales are declining
    risk_kinds = {r["kind"] for r in detect_risks(db, business)}
    base = _baseline(db, business)
    if "declining_sales" in risk_kinds or "customer_churn" in risk_kinds:
        sim = simulate(base, Levers(marketing_change_pct=30))
        cur = simulate(base, Levers())
        gain = sim["profit"] - cur["profit"]
        propose(Decision(
            business_id=business.id, key=f"marketing:{date.today().strftime('%Y-%m')}",
            kind="marketing",
            title="Boost marketing 30% for three weeks",
            detail=f"Sales/footfall are trending down. The simulator predicts revenue "
                   f"{sim['deltas']['revenue_pct']:+.1f}% and profit ₹{gain:+,.0f}/month at +30% marketing spend.",
            expected_impact=f"₹{gain:+,.0f}/month simulated profit change",
            impact_inr=round(gain),
            action_type="advice", action_json="{}",
        ))

    # 5. Postpone low-priority spending when cash-negative
    if "negative_cash_flow" in risk_kinds:
        sim = simulate(base, Levers(opex_change_pct=-8, inventory_change_pct=-10))
        cur = simulate(base, Levers())
        gain = sim["profit"] - cur["profit"]
        propose(Decision(
            business_id=business.id, key=f"spending:{date.today().strftime('%Y-%m')}",
            kind="spending",
            title="Postpone low-priority spending (−8% opex, −10% inventory buy)",
            detail=f"Cash flow is negative. Deferring non-essential spend is simulated to "
                   f"improve monthly profit by ₹{gain:+,.0f} with minimal demand impact.",
            expected_impact=f"₹{gain:+,.0f}/month simulated cash relief",
            impact_inr=round(gain),
            action_type="advice", action_json="{}",
        ))

    return created


def apply_decision(db: Database, business: Business, decision: Decision) -> str:
    """Execute an approved decision. Returns a result note."""
    payload = json.loads(decision.action_json or "{}")
    if decision.action_type == "update_price":
        p = db.products.find_one({"_id": oid(payload["product_id"]), "business_id": business.id})
        if not p:
            return "Product no longer exists — nothing changed."
        db.products.update_one({"_id": p["_id"]}, {"$set": {"price": float(payload["new_price"])}})
        return f"Price updated: {p['name']} ₹{p['price']:g} → ₹{payload['new_price']:g}."
    if decision.action_type == "log_order":
        p = db.products.find_one({"_id": oid(payload["product_id"]), "business_id": business.id})
        if not p:
            return "Product no longer exists — nothing changed."
        db.products.update_one({"_id": p["_id"]}, {"$set": {"reorder_qty": int(payload["qty"])}})
        return (f"Order approved: {payload['qty']} units of {p['name']}. Reorder quantity saved — "
                f"update the stock in Products when the delivery arrives.")
    return "Approved — recorded in the decision log."


def decide(db: Database, business: Business, decision_id: str, approve: bool) -> dict:
    doc = db.decisions.find_one({"_id": oid(decision_id), "business_id": business.id})
    if not doc:
        return {"ok": False, "error": "Decision not found"}
    decision = Decision.from_doc(doc)
    if decision.status != "pending":
        return {"ok": False, "error": f"Already {decision.status}"}
    note = apply_decision(db, business, decision) if approve else "Rejected — won't be re-proposed for two weeks."
    db.decisions.update_one({"_id": oid(decision_id)}, {"$set": {
        "status": "approved" if approve else "rejected",
        "decided_at": dt.now(timezone.utc), "result_note": note}})
    return {"ok": True, "status": "approved" if approve else "rejected", "result_note": note}


def list_decisions(db: Database, business: Business) -> dict:
    generate_decisions(db, business)
    rows = find_models(db, Decision, {"business_id": business.id},
                       sort=[("created_at", -1)], limit=40)
    out = [{"id": d.id, "kind": d.kind, "title": d.title, "detail": d.detail,
            "expected_impact": d.expected_impact, "impact_inr": d.impact_inr,
            "action_type": d.action_type, "status": d.status, "result_note": d.result_note,
            "created_at": d.created_at.isoformat(),
            "decided_at": d.decided_at.isoformat() if d.decided_at else None} for d in rows]
    pending = [d for d in out if d["status"] == "pending"]
    return {
        "decisions": out,
        "pending_count": len(pending),
        "pending_impact_inr": round(sum(d["impact_inr"] for d in pending)),
        "note": "Every proposal is simulated before it reaches this inbox. Price approvals apply "
                "immediately; restock approvals record the order for you to place.",
    }
