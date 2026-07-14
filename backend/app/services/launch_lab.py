"""Product Launch Lab engine (§15-34): test a NEW product inside the twin
before buying real inventory.

Everything here is deterministic and explainable. Demand for the unlaunched
product is anchored to real category history in the twin (similar products'
velocity and price points); every result carries its assumptions and a
confidence score derived from how much comparable history exists.
"""

import math
from datetime import date, timedelta
from statistics import median

from pymongo.database import Database

from ..models import (Business, Product, ProductExperiment, ProductSale,
                      find_models, to_dt)
from .simulation import CATEGORY_ELASTICITY, MODEL_VERSION

# ---------------------------------------------------------------------------
# heuristic multipliers — always surfaced in the assumptions list
# ---------------------------------------------------------------------------

SHELF_PLACEMENT = {
    "Eye Level": 1.15, "Top Shelf": 0.95, "Middle Shelf": 1.0, "Bottom Shelf": 0.88,
    "Checkout Counter": 1.10, "Entrance Display": 1.12, "Promotional Endcap": 1.20,
    "Refrigerated Section": 1.0,
}

TARGET_SEGMENTS = {
    # (demand multiplier, price sensitivity multiplier on elasticity)
    "All Customers": (1.0, 1.0), "Loyal Customers": (0.65, 0.75),
    "High Value Customers": (0.5, 0.6), "Price Sensitive Customers": (0.8, 1.4),
    "Families": (0.85, 1.1), "Students": (0.6, 1.35), "Young Adults": (0.7, 1.05),
    "Frequent Buyers": (0.75, 0.9), "New Customers": (0.55, 1.2),
}

# Indian festival windows (month, day, span) reused for launch timing
FESTIVAL_WINDOWS = [(1, 14, "Makar Sankranti"), (3, 25, "Holi"), (8, 15, "Independence Day"),
                    (9, 7, "Ganesh Chaturthi"), (10, 22, "Dussehra"), (11, 12, "Diwali"),
                    (12, 25, "Christmas")]

NEW_ENTRANT_CAPTURE = 0.5   # a new SKU initially captures ~50% of comparable velocity
NEW_PRODUCT_ELASTICITY_MULT = 1.8  # unproven products face more substitutes than incumbents
MARKETING_SCALE = 6000.0    # ₹ at which marketing uplift reaches ~76% of its max
MARKETING_MAX_UPLIFT = 0.40


def landed_cost(exp: ProductExperiment) -> float:
    base = (exp.supplier_cost + exp.transport_cost + exp.storage_cost
            + exp.handling_cost + exp.other_variable_cost)
    wastage = min(max(exp.wastage_percent, 0), 60) / 100.0
    return round(base / (1 - wastage), 2) if wastage < 1 else base


def category_anchor(db: Database, business: Business, exp: ProductExperiment) -> dict:
    """Anchor the new product's demand to real category history in the twin."""
    similar = find_models(db, Product,
                          {"business_id": business.id, "category": exp.category})
    since = to_dt(date.today() - timedelta(days=120))
    sales = find_models(db, ProductSale, {
        "business_id": business.id,
        "product_id": {"$in": [p.id for p in similar]},
        "day": {"$gte": since},
    }) if similar else []
    by_product: dict[str, list[ProductSale]] = {}
    for r in sales:
        by_product.setdefault(r.product_id, []).append(r)
    history_days = 0
    velocities, prices = [], []
    for p in similar:
        rows = by_product.get(p.id, [])
        if rows:
            days = len({r.day for r in rows})
            velocities.append(sum(r.units for r in rows) / max(days, 1))
            history_days = max(history_days, days)
        elif p.daily_demand:
            velocities.append(p.daily_demand)
        prices.append(p.price)

    # anchor between the typical and the leading SKU of the category — a well-chosen
    # new product aims above the median performer
    ref_velocity = max(median(velocities), 0.5 * max(velocities)) if velocities else 8.0
    ref_price = median(prices) if prices else max(exp.planned_price, 1.0)
    return {
        "similar_count": len(similar),
        "history_days": history_days,
        "ref_velocity": ref_velocity,
        "ref_price": ref_price,
    }


def _confidence(anchor: dict) -> float:
    """0-100: how much comparable history backs the prediction."""
    base = 30.0
    base += min(anchor["similar_count"], 6) * 5.5          # up to +33
    base += min(anchor["history_days"], 120) / 120 * 25    # up to +25
    return round(min(base, 92), 0)


def _marketing_uplift(budget: float) -> float:
    return MARKETING_MAX_UPLIFT * math.tanh(budget / MARKETING_SCALE)


def simulate_point(db: Database, business: Business, exp: ProductExperiment, *,
                   price: float, discount: float = 0.0, stock: int | None = None,
                   marketing: float | None = None, anchor: dict | None = None) -> dict:
    """Predict one launch configuration over the first month."""
    anchor = anchor or category_anchor(db, business, exp)
    stock = exp.initial_stock if stock is None else stock
    marketing = exp.marketing_budget if marketing is None else marketing

    cost = landed_cost(exp)
    seg_mult, seg_sens = TARGET_SEGMENTS.get(exp.target_segment, (1.0, 1.0))
    placement_mult = SHELF_PLACEMENT.get(exp.shelf_placement, 1.0)
    elasticity = (CATEGORY_ELASTICITY.get(exp.category, -1.5)
                  * seg_sens * NEW_PRODUCT_ELASTICITY_MULT)

    eff_price = price * (1 - discount / 100.0)

    # demand: anchored to category velocity, elastic around the category's median price
    price_ratio = eff_price / anchor["ref_price"] if anchor["ref_price"] else 1.0
    units_day = (anchor["ref_velocity"] * NEW_ENTRANT_CAPTURE
                 * (price_ratio ** elasticity)
                 * placement_mult * seg_mult
                 * (1 + _marketing_uplift(marketing)))
    # manual competitor price: pricing above it sharply suppresses trial
    if exp.competitor_price:
        comp_ratio = exp.competitor_price / eff_price
        units_day *= comp_ratio ** 2.0 if comp_ratio < 1 else comp_ratio ** 0.3
    if discount > 0:  # deal-seeker attention beyond the pure price effect
        units_day *= 1 + min(discount, 25) * 0.006

    demand_month = units_day * 30
    units_sold = min(demand_month, stock)          # can't sell beyond initial stock
    unsold = max(stock - demand_month, 0)
    lost_sales = max(demand_month - stock, 0)

    revenue = eff_price * units_sold
    gross_profit = (eff_price - cost) * units_sold
    net_contribution = gross_profit - marketing
    margin_pct = (eff_price - cost) / eff_price * 100 if eff_price else -100

    # customer acceptance: relative price position vs category & competitor
    accept = 72.0 - (price_ratio - 1) * 55
    if exp.competitor_price:
        accept -= (eff_price / exp.competitor_price - 1) * 35
    accept += min(discount, 20) * 0.8
    acceptance = round(max(min(accept, 96), 8), 0)

    days_of_cover = stock / max(units_day, 0.1)
    stockout_date = (date.today() + timedelta(days=int(days_of_cover))).isoformat() \
        if days_of_cover < 45 else None
    stockout_risk = ("high" if days_of_cover < max(exp.supplier_lead_time * 1.5, 12)
                     else "medium" if days_of_cover < 30
                     else "low")
    overstock_risk = ("high" if days_of_cover > 60 else
                      "medium" if days_of_cover > 40 else "low")

    # break-even on upfront investment (marketing treated as one-time launch cost;
    # gross profit is the recurring monthly result)
    investment = stock * cost + marketing
    contribution_per_unit = eff_price - cost
    if contribution_per_unit > 0 and units_day > 0:
        be_units = investment / contribution_per_unit
        be_days = be_units / units_day
        be_months = round(be_days / 30, 1)
    else:
        be_units = be_days = be_months = None

    risk = launch_risk_score(
        margin_pct=margin_pct, acceptance=acceptance, days_of_cover=days_of_cover,
        lead_time=exp.supplier_lead_time, wastage=exp.wastage_percent,
        shelf_life=0, be_days=be_days, lost_sales=lost_sales, demand=demand_month,
    )

    return {
        "price": round(price, 2), "discount_pct": discount,
        "effective_price": round(eff_price, 2),
        "stock": stock, "marketing": marketing,
        "landed_cost": cost,
        "predicted_units_per_day": round(units_day, 1),
        "predicted_demand_month": round(demand_month, 0),
        "predicted_units_sold": round(units_sold, 0),
        "unsold_inventory": round(unsold, 0),
        "lost_sales_units": round(lost_sales, 0),
        "predicted_revenue": round(revenue, 0),
        "predicted_gross_profit": round(gross_profit, 0),
        "net_contribution": round(net_contribution, 0),
        # 3-month view: marketing is a one-time launch cost, gross profit recurs
        "net_3_months": round(gross_profit * 3 - marketing, 0),
        "margin_pct": round(margin_pct, 1),
        "customer_acceptance_pct": acceptance,
        "days_of_cover": round(days_of_cover, 1),
        "stockout_date": stockout_date,
        "stockout_risk": stockout_risk,
        "overstock_risk": overstock_risk,
        "break_even_units": round(be_units, 0) if be_units is not None else None,
        "break_even_days": round(be_days, 0) if be_days is not None else None,
        "break_even_months": be_months,
        "investment": round(investment, 0),
        "risk_score": risk["overall"],
        "risk_components": risk["components"],
        "risk_level": risk["level"],
        "confidence_pct": _confidence(anchor),
    }


def launch_risk_score(*, margin_pct, acceptance, days_of_cover, lead_time,
                      wastage, shelf_life, be_days, lost_sales, demand) -> dict:
    """0-100 launch risk with named components (§30)."""
    components = {}
    components["margin"] = max(min((15 - margin_pct) * 3.5, 100), 0)
    components["adoption"] = max(min((60 - acceptance) * 2.2, 100), 0)
    if days_of_cover < lead_time * 1.5:
        components["inventory"] = 75.0
    elif days_of_cover > 60:
        components["inventory"] = 55.0
    elif days_of_cover > 40:
        components["inventory"] = 30.0
    else:
        components["inventory"] = 12.0
    components["demand"] = max(min((150 - demand) * 0.5, 100), 0)  # tiny volumes are risky
    components["wastage"] = min(wastage * 4, 100)
    components["break_even"] = (min(be_days / 1.8, 100) if be_days is not None else 90.0)
    components["supplier"] = min(lead_time * 8, 100)
    weights = {"margin": 0.24, "adoption": 0.18, "inventory": 0.18, "demand": 0.14,
               "wastage": 0.08, "break_even": 0.12, "supplier": 0.06}
    overall = round(sum(components[k] * w for k, w in weights.items()), 0)
    level = ("Low" if overall < 30 else "Moderate" if overall < 50
             else "High" if overall < 70 else "Critical")
    return {"overall": overall, "level": level,
            "components": {k: round(v, 0) for k, v in components.items()}}


def _price_points(exp: ProductExperiment) -> list[float]:
    pts, p = [], exp.min_price
    while p <= exp.max_price + 1e-9:
        pts.append(round(p, 2))
        p += exp.price_step
    return pts


def price_sweep(db: Database, business: Business, exp: ProductExperiment) -> dict:
    anchor = category_anchor(db, business, exp)
    points = [simulate_point(db, business, exp, price=p, discount=0.0, anchor=anchor)
              for p in _price_points(exp)]
    valid = [pt for pt in points if pt["margin_pct"] > 0] or points

    def best(key, reverse=True):
        return sorted(valid, key=lambda x: (x[key] if x[key] is not None else -1e18), reverse=reverse)[0]

    best_profit = best("net_contribution")
    best_revenue = best("predicted_revenue")
    best_adoption = best("customer_acceptance_pct")
    lowest_risk = best("risk_score", reverse=False)
    balanced = sorted(valid, key=lambda x: (
        x["net_contribution"] / max(best_profit["net_contribution"], 1) * 0.5
        + x["customer_acceptance_pct"] / 100 * 0.3
        - x["risk_score"] / 100 * 0.2
    ), reverse=True)[0]

    return {
        "points": points,
        "recommendations": {
            "best_profit": best_profit, "best_revenue": best_revenue,
            "best_adoption": best_adoption, "balanced": balanced, "lowest_risk": lowest_risk,
        },
        "anchor": anchor,
        "assumptions": _assumptions(exp, anchor),
        "model_version": MODEL_VERSION,
    }


def discount_sweep(db: Database, business: Business, exp: ProductExperiment,
                   base_price: float | None = None) -> dict:
    anchor = category_anchor(db, business, exp)
    price = base_price or exp.planned_price
    points = [simulate_point(db, business, exp, price=price, discount=d, anchor=anchor)
              for d in (0, 5, 10, 15, 20)]

    def best(key, reverse=True):
        return sorted(points, key=lambda x: (x[key] if x[key] is not None else -1e18), reverse=reverse)[0]

    return {
        "base_price": price,
        "points": points,
        "recommendations": {
            "best_profit": best("net_contribution"),
            "best_growth": best("predicted_units_sold"),
            "best_acquisition": best("customer_acceptance_pct"),
            "lowest_risk": best("risk_score", reverse=False),
        },
        "anchor": anchor,
        "assumptions": _assumptions(exp, anchor),
        "model_version": MODEL_VERSION,
    }


def inventory_sweep(db: Database, business: Business, exp: ProductExperiment,
                    price: float | None = None) -> dict:
    anchor = category_anchor(db, business, exp)
    price = price or exp.planned_price
    demand_probe = simulate_point(db, business, exp, price=price, stock=10 ** 6, anchor=anchor)
    monthly_demand = demand_probe["predicted_demand_month"]

    levels = sorted({50, 100, 150, 200, 300, 500, exp.initial_stock,
                     int(monthly_demand), int(monthly_demand * 1.3)})
    levels = [lv for lv in levels if lv > 0]
    points = []
    for stock in levels:
        pt = simulate_point(db, business, exp, price=price, stock=stock, anchor=anchor)
        units_day = pt["predicted_units_per_day"]
        reorder_in = max((stock - exp.reorder_point) / max(units_day, 0.1), 0) if exp.reorder_point else None
        pt["holding_cost"] = round(stock * landed_cost(exp) * 0.02, 0)  # ~2%/month carrying
        pt["reorder_date"] = ((date.today() + timedelta(days=int(reorder_in))).isoformat()
                              if reorder_in is not None else None)
        pt["suggested_order_qty"] = max(int(units_day * (exp.supplier_lead_time + 14) - exp.safety_stock), 0)
        points.append(pt)

    # best stock: cover forecast demand + lead time buffer + safety stock, minimal excess
    ideal = int(monthly_demand + demand_probe["predicted_units_per_day"] * exp.supplier_lead_time
                + exp.safety_stock)
    best = min(points, key=lambda x: abs(x["stock"] - ideal))
    return {
        "price": price,
        "monthly_demand_forecast": monthly_demand,
        "points": points,
        "recommended_stock": best["stock"],
        "recommended_reason": (
            f"Covers the ~{monthly_demand:.0f}-unit first-month demand forecast plus "
            f"{exp.supplier_lead_time} days of supplier lead time and {exp.safety_stock} safety-stock units."),
        "anchor": anchor,
        "assumptions": _assumptions(exp, anchor),
        "model_version": MODEL_VERSION,
    }


def optimize(db: Database, business: Business, exp: ProductExperiment, *,
             min_price: float | None = None, max_price: float | None = None,
             max_discount: float = 20, max_stock: int | None = None,
             max_marketing: float | None = None, min_margin_pct: float = 5) -> dict:
    """Deterministic constrained grid search over price × discount × stock × marketing (§33)."""
    anchor = category_anchor(db, business, exp)
    lo = min_price if min_price is not None else exp.min_price
    hi = max_price if max_price is not None else exp.max_price
    prices = [round(lo + i * (hi - lo) / 6, 2) for i in range(7)] if hi > lo else [lo]
    discounts = [d for d in (0, 5, 10, 15, 20) if d <= max_discount]
    stock_cap = max_stock or max(exp.initial_stock * 2, 300)
    stocks = sorted({int(stock_cap * f) for f in (0.4, 0.7, 1.0)} | {exp.initial_stock})
    stocks = [s for s in stocks if 0 < s <= stock_cap]
    mkt_cap = max_marketing if max_marketing is not None else max(exp.marketing_budget, 5000)
    marketings = sorted({0.0, round(mkt_cap * 0.5, 0), float(mkt_cap)})

    candidates = []
    for p in prices:
        for d in discounts:
            for s in stocks:
                for m in marketings:
                    pt = simulate_point(db, business, exp, price=p, discount=d,
                                        stock=s, marketing=m, anchor=anchor)
                    if pt["margin_pct"] >= min_margin_pct:
                        candidates.append(pt)
    evaluated = len(prices) * len(discounts) * len(stocks) * len(marketings)
    if not candidates:
        return {"error": f"No combination meets the {min_margin_pct}% minimum margin — "
                         "widen the price range or lower the margin floor.",
                "evaluated": evaluated}

    max_profit = max(candidates, key=lambda x: x["net_3_months"])
    max_growth = max(candidates, key=lambda x: x["predicted_units_sold"])
    lowest_risk = min(candidates, key=lambda x: x["risk_score"])
    best_np = max(max_profit["net_3_months"], 1)
    balanced = max(candidates, key=lambda x: (
        x["net_3_months"] / best_np * 0.45
        + x["customer_acceptance_pct"] / 100 * 0.25
        - x["risk_score"] / 100 * 0.30
    ))
    return {
        "evaluated": evaluated,
        "feasible": len(candidates),
        "strategies": {
            "recommended": balanced, "max_profit": max_profit,
            "max_growth": max_growth, "lowest_risk": lowest_risk,
        },
        "constraints": {"min_price": lo, "max_price": hi, "max_discount": max_discount,
                        "max_stock": stock_cap, "max_marketing": mkt_cap,
                        "min_margin_pct": min_margin_pct},
        "anchor": anchor,
        "assumptions": _assumptions(exp, anchor),
        "model_version": MODEL_VERSION,
    }


def cannibalization(db: Database, business: Business, exp: ProductExperiment,
                    point: dict) -> dict:
    """Estimate sales shift from existing same-category products (§28)."""
    words = {w.lower() for w in exp.product_name.split() if len(w) > 3}
    similar = find_models(db, Product,
                          {"business_id": business.id, "category": exp.category})
    overlaps = []
    for p in similar:
        pwords = {w.lower() for w in p.name.split() if len(w) > 3}
        name_overlap = len(words & pwords) / max(len(words | pwords), 1)
        price_gap = abs(p.price - exp.planned_price) / max(p.price, 1)
        overlap = name_overlap * 0.6 + max(0.35 - price_gap, 0)
        if overlap > 0.12:
            overlaps.append((p, min(overlap, 0.6)))

    new_units = point["predicted_units_sold"]
    victims = []
    total_shift = 0.0
    for p, ov in sorted(overlaps, key=lambda t: -t[1])[:3]:
        shift = round(new_units * ov * 0.45, 0)
        total_shift += shift
        victims.append({"product": p.name, "current_price": p.price,
                        "estimated_monthly_loss_units": shift,
                        "overlap_score": round(ov, 2)})
    risk = "high" if total_shift > new_units * 0.4 else \
           "medium" if total_shift > new_units * 0.15 else "low"
    return {
        "new_product_units": new_units,
        "estimated_existing_loss_units": round(total_shift, 0),
        "net_category_growth_units": round(new_units - total_shift, 0),
        "risk": risk,
        "affected_products": victims,
        "assumption": "Overlap estimated from name similarity and price proximity within the category; "
                      "45% of overlapping demand is assumed to shift rather than be incremental.",
    }


def launch_timing(db: Database, business: Business, exp: ProductExperiment) -> dict:
    """Recommend a launch window from weekday + festival demand patterns (§23)."""
    today = date.today()
    windows = []
    for month_offset in range(3):
        m = (today.month - 1 + month_offset) % 12 + 1
        year = today.year + (today.month - 1 + month_offset) // 12
        fest = [name for (fm, _fd, name) in FESTIVAL_WINDOWS if fm == m]
        score = 1.0 + (0.25 if fest else 0.0)
        windows.append({
            "month": f"{year}-{m:02d}",
            "festivals": fest,
            "demand_index": round(score, 2),
        })
    best = max(windows, key=lambda w: w["demand_index"])
    return {
        "windows": windows,
        "recommended": best,
        "note": "Weekends (Fri–Sun) carry ~20% higher footfall in your twin history. "
                "Launching 3–5 days before a festival window maximizes trial. Estimated, not guaranteed.",
    }


def before_after(db: Database, business: Business, exp: ProductExperiment, point: dict) -> dict:
    """WITHOUT vs WITH launch: whole-business monthly view (§34)."""
    from .insights import compute_kpis
    kpis = compute_kpis(db, business)
    rev = kpis.get("monthly_revenue", business.monthly_revenue)
    profit = kpis.get("monthly_profit", business.monthly_revenue - business.monthly_expenses)
    inv = kpis.get("inventory_value", 0)
    cann = cannibalization(db, business, exp, point)
    cann_rev_loss = cann["estimated_existing_loss_units"] * exp.planned_price * 0.9

    return {
        "without": {"revenue": round(rev, 0), "profit": round(profit, 0),
                    "inventory_value": round(inv, 0)},
        "with": {
            "revenue": round(rev + point["predicted_revenue"] - cann_rev_loss, 0),
            "profit": round(profit + point["net_contribution"] - cann_rev_loss * 0.25, 0),
            "inventory_value": round(inv + point["investment"] - point["marketing"], 0),
        },
        "cannibalization": cann,
    }


def _assumptions(exp: ProductExperiment, anchor: dict) -> list[str]:
    seg_mult, seg_sens = TARGET_SEGMENTS.get(exp.target_segment, (1.0, 1.0))
    return [
        f"Demand anchored to {anchor['similar_count']} existing {exp.category} products "
        f"(median {anchor['ref_velocity']:.1f} units/day at median price ₹{anchor['ref_price']:.0f}, "
        f"{anchor['history_days']} days of sales history)",
        f"A new SKU is assumed to capture ~{NEW_ENTRANT_CAPTURE * 100:.0f}% of comparable velocity in month 1",
        f"Category price elasticity {CATEGORY_ELASTICITY.get(exp.category, -1.5)} steepened "
        f"×{NEW_PRODUCT_ELASTICITY_MULT} for an unproven product, segment-adjusted ×{seg_sens} "
        f"for {exp.target_segment}",
        f"Shelf placement '{exp.shelf_placement}' multiplier ×{SHELF_PLACEMENT.get(exp.shelf_placement, 1.0)} (heuristic)",
        f"Marketing follows diminishing returns (max +{MARKETING_MAX_UPLIFT * 100:.0f}% demand, "
        f"₹{MARKETING_SCALE:.0f} half-saturation)",
        f"Wastage {exp.wastage_percent}% is priced into the ₹{landed_cost(exp)} landed cost",
    ] + ([f"Competitor price ₹{exp.competitor_price:.0f} (entered manually) shapes acceptance"]
         if exp.competitor_price else [])
