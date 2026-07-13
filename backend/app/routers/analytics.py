from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, DailyMetric, Product, ProductSale
from ..security import get_current_business
from ..services.insights import compute_kpis, health_score, twin_status

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _series(db: Session, business_id: int, days: int) -> list[DailyMetric]:
    since = date.today() - timedelta(days=days)
    return (
        db.query(DailyMetric)
        .filter(DailyMetric.business_id == business_id, DailyMetric.day >= since)
        .order_by(DailyMetric.day)
        .all()
    )


@router.get("/dashboard")
def dashboard(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    kpis = compute_kpis(db, business)
    health = health_score(db, business)
    rows = _series(db, business.id, 90)

    trend = [
        {"day": r.day.isoformat(), "revenue": r.revenue, "expenses": r.expenses,
         "profit": round(r.revenue - r.expenses, 0), "customers": r.customers, "orders": r.orders}
        for r in rows
    ]

    # weekly aggregation for smoother long-range charts
    weekly = defaultdict(lambda: {"revenue": 0.0, "expenses": 0.0, "customers": 0})
    for r in rows:
        week = (r.day - timedelta(days=r.day.weekday())).isoformat()
        weekly[week]["revenue"] += r.revenue
        weekly[week]["expenses"] += r.expenses
        weekly[week]["customers"] += r.customers
    weekly_trend = [
        {"week": k, "revenue": round(v["revenue"], 0), "expenses": round(v["expenses"], 0),
         "profit": round(v["revenue"] - v["expenses"], 0), "customers": v["customers"]}
        for k, v in sorted(weekly.items())
    ][:-1]  # drop incomplete current week

    # top products (last 30 days)
    since = date.today() - timedelta(days=30)
    top = (
        db.query(Product.name, func.sum(ProductSale.units).label("units"),
                 func.sum(ProductSale.revenue).label("revenue"))
        .join(Product, Product.id == ProductSale.product_id)
        .filter(ProductSale.business_id == business.id, ProductSale.day >= since)
        .group_by(Product.name)
        .order_by(func.sum(ProductSale.revenue).desc())
        .limit(7)
        .all()
    )

    # peak hours profile (derived deterministic curve scaled to real footfall)
    hours = list(range(9, 22))
    weights = [3, 5, 7, 9, 8, 5, 4, 5, 7, 10, 12, 9, 6]
    daily_customers = kpis.get("monthly_customers", 0) / 30 if kpis else 40
    peak = [
        {"hour": f"{h}:00", "customers": round(daily_customers * w / sum(weights))}
        for h, w in zip(hours, weights)
    ]

    return {
        "kpis": kpis,
        "health": health,
        "twin_status": twin_status(db, business),
        "trend": trend,
        "weekly_trend": weekly_trend,
        "top_products": [{"name": n, "units": int(u or 0), "revenue": float(r or 0)} for n, u, r in top],
        "peak_hours": peak,
    }


@router.get("/finance")
def finance(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    rows = _series(db, business.id, 365)
    monthly = defaultdict(lambda: {"revenue": 0.0, "expenses": 0.0})
    for r in rows:
        key = r.day.strftime("%Y-%m")
        monthly[key]["revenue"] += r.revenue
        monthly[key]["expenses"] += r.expenses
    months = [
        {"month": k, "revenue": round(v["revenue"], 0), "expenses": round(v["expenses"], 0),
         "profit": round(v["revenue"] - v["expenses"], 0),
         "margin_pct": round((v["revenue"] - v["expenses"]) / v["revenue"] * 100, 1) if v["revenue"] else 0}
        for k, v in sorted(monthly.items())
    ]

    last30 = rows[-30:]
    rev = sum(r.revenue for r in last30) or 1
    exp = sum(r.expenses for r in last30)
    profit = rev - exp
    # expense composition estimate (COGS / payroll / marketing / other)
    breakdown = [
        {"name": "Cost of Goods", "value": round(exp * 0.55, 0)},
        {"name": "Payroll", "value": round(min(business.employees_count * 18000, exp * 0.3), 0)},
        {"name": "Marketing", "value": round(exp * 0.05, 0)},
        {"name": "Rent & Utilities", "value": round(exp * 0.12, 0)},
    ]
    breakdown.append({"name": "Other", "value": round(max(exp - sum(b["value"] for b in breakdown), 0), 0)})

    fixed_costs = exp * 0.35
    contribution = 1 - 0.55  # revenue share left after variable costs
    breakeven_revenue = fixed_costs / contribution

    cumulative, cash_flow = 0.0, []
    for r in last30:
        cumulative += r.revenue - r.expenses
        cash_flow.append({"day": r.day.isoformat(), "net": round(r.revenue - r.expenses, 0),
                          "cumulative": round(cumulative, 0)})

    return {
        "monthly": months,
        "breakdown": breakdown,
        "cash_flow": cash_flow,
        "summary": {
            "revenue": round(rev, 0), "expenses": round(exp, 0), "profit": round(profit, 0),
            "margin_pct": round(profit / rev * 100, 1),
            "roi_pct": round(profit / exp * 100, 1) if exp else 0,
            "breakeven_revenue": round(breakeven_revenue, 0),
            "breakeven_reached": rev >= breakeven_revenue,
        },
    }


@router.get("/customers")
def customers(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    rows = _series(db, business.id, 180)
    trend = [
        {"day": r.day.isoformat(), "customers": r.customers, "new_customers": r.new_customers,
         "returning": max(r.customers - r.new_customers, 0)}
        for r in rows
    ]
    last30 = rows[-30:]
    total = sum(r.customers for r in last30) or 1
    new = sum(r.new_customers for r in last30)
    rev = sum(r.revenue for r in last30)
    retention = round((1 - new / total) * 100, 1)
    avg_ticket = rev / max(sum(r.orders for r in last30), 1)
    visits_per_customer = total / max(business.customer_count, 1)
    clv = avg_ticket * visits_per_customer * 12  # 12-month horizon

    # ---- aggregate segment estimate (no individual customer records) -------
    # Shares are derived from retention and new-customer mix; clearly labeled
    # in the UI as "aggregate estimate", never per-person predictions.
    ret_frac = retention / 100
    churn_frac = 1 - ret_frac
    segments = [
        {"name": "Loyal", "share_pct": round(ret_frac * 42, 1),
         "behaviour": "Visit weekly+, low price sensitivity, first to adopt new products"},
        {"name": "Regular", "share_pct": round(ret_frac * 34, 1),
         "behaviour": "Visit 1-2×/month, moderate price sensitivity"},
        {"name": "Occasional", "share_pct": round(ret_frac * 24, 1),
         "behaviour": "Irregular visits, respond mainly to offers"},
        {"name": "New", "share_pct": round(new / total * 100, 1),
         "behaviour": "First 30 days — retention decided by first 2-3 experiences"},
        {"name": "At Risk", "share_pct": round(min(churn_frac * 55, 30), 1),
         "behaviour": "Declining visit frequency — win back with targeted offers"},
    ]

    # elasticity-grounded behaviour predictions at the aggregate level
    from ..services.simulation import PRICE_ELASTICITY
    elasticity = PRICE_ELASTICITY.get(business.business_type, -1.5)
    predictions = {
        "return_probability_pct": round(ret_frac * 100 * 0.92, 0),
        "discount_response": f"A 10% offer is predicted to lift demand ~{abs(elasticity) * 8 * 0.8:.0f}%",
        "price_increase_response": f"A 5% price rise is predicted to cost ~{abs(elasticity) * 5:.0f}% of demand",
        "new_product_adoption_pct": round(28 + ret_frac * 30, 0),
        "label": ("Aggregate estimate from daily footfall history — "
                  "no individual customer records are used."),
    }
    return {
        "trend": trend,
        "summary": {
            "monthly_customers": total, "new_customers": new,
            "retention_pct": retention, "churn_pct": round(100 - retention, 1),
            "avg_ticket": round(avg_ticket, 0), "clv": round(clv, 0),
        },
        "segments": segments,
        "predictions": predictions,
    }
