"""AI Business Time Machine: replay the twin as of any past date, with
deterministic explanations of what moved the numbers.

Explanations are inferred from the twin's own history:
- revenue anomalies vs a weekday-matched baseline,
- likely stockouts (a normally-selling product going silent for days),
- festival windows from the demand calendar.

Per-product stock levels aren't stored historically, so the replay also
snapshots today's stock on every visit — the archive gets richer over time.
"""

from datetime import date, datetime, timedelta

import numpy as np
from pymongo.database import Database

from ..models import Business, DailyMetric, ProductSale, find_models, to_dt
from .insights import _business_products
from .intelligence import FESTIVALS, WEEKDAYS


def snapshot_today_stock(db: Database, business: Business) -> None:
    """Archive today's per-product stock so future replays can show real shelves."""
    products = _business_products(db, business.id)
    if not products:
        return
    db.stock_snapshots.update_one(
        {"business_id": business.id, "day": to_dt(date.today())},
        {"$set": {"products": [
            {"product_id": p.id, "name": p.name, "stock": p.stock,
             "daily_demand": p.daily_demand} for p in products]}},
        upsert=True,
    )


def _window(db: Database, business_id: str, end: date, days: int) -> list[DailyMetric]:
    return find_models(
        db, DailyMetric,
        {"business_id": business_id,
         "day": {"$gte": to_dt(end - timedelta(days=days - 1)), "$lte": to_dt(end)}},
        sort=[("day", 1)],
    )


def _festival_near(d: date) -> tuple[str, int] | None:
    for month, day, name, span in FESTIVALS:
        peak = date(d.year, month, day)
        if abs((d - peak).days) <= span:
            return name, (d - peak).days
    return None


def _detect_events(rows90: list[DailyMetric], sales: list[ProductSale],
                   window_start: date, window_end: date,
                   name_of: dict[str, str]) -> list[dict]:
    """Explainable events inside [window_start, window_end]."""
    events: list[dict] = []

    # weekday-matched revenue baseline over the full 90-day context
    wd: dict[int, list[float]] = {}
    for r in rows90:
        wd.setdefault(r.day.weekday(), []).append(r.revenue)
    wd_mean = {k: float(np.mean(v)) for k, v in wd.items()}

    for r in rows90:
        if not window_start <= r.day <= window_end:
            continue
        base = wd_mean.get(r.day.weekday(), 0)
        if not base:
            continue
        dev = r.revenue / base - 1
        fest = _festival_near(r.day)
        if dev >= 0.22:
            events.append({
                "day": r.day.isoformat(), "kind": "spike", "tone": "good",
                "title": f"Revenue spike {dev * 100:+.0f}%",
                "detail": (f"₹{r.revenue:,.0f} vs a typical {WEEKDAYS[r.day.weekday()]} of ₹{base:,.0f}"
                           + (f" — inside the {fest[0]} window." if fest else ".")),
            })
        elif dev <= -0.22:
            events.append({
                "day": r.day.isoformat(), "kind": "dip", "tone": "bad",
                "title": f"Revenue dip {dev * 100:+.0f}%",
                "detail": f"₹{r.revenue:,.0f} vs a typical {WEEKDAYS[r.day.weekday()]} of ₹{base:,.0f}.",
            })

    # likely stockouts: products that normally sell most days but went silent ≥3 days
    by_product: dict[str, dict[date, int]] = {}
    for s in sales:
        by_product.setdefault(s.product_id, {})
        by_product[s.product_id][s.day] = by_product[s.product_id].get(s.day, 0) + s.units

    if sales:
        span_days = [window_start + timedelta(days=i)
                     for i in range((window_end - window_start).days + 1)]
        for pid, all_days in by_product.items():
            if len(all_days) < 20:  # not a regular seller — silence proves nothing
                continue
            name = name_of.get(pid, "A product")
            typical_units = float(np.mean(list(all_days.values())))
            run, run_start = 0, None
            for d in span_days:
                if d not in all_days:
                    run += 1
                    run_start = run_start or d
                else:
                    if run >= 3:
                        events.append(_gap_event(name, run_start, run, typical_units))
                    run, run_start = 0, None
            if run >= 3 and run_start:
                events.append(_gap_event(name, run_start, run, typical_units))

    events.sort(key=lambda e: e["day"], reverse=True)
    return events[:8]


def _gap_event(name: str, start: date, days: int, typical_units: float) -> dict:
    return {
        "day": start.isoformat(), "kind": "stockout", "tone": "bad",
        "title": f"{name}: no sales for {days} days (likely stockout)",
        "detail": (f"This product normally sells ~{typical_units:.0f} units/day; {days} silent days "
                   f"from {start.strftime('%d %b')} cost roughly {typical_units * days:.0f} lost units."),
    }


def replay(db: Database, business: Business, on_date: date) -> dict:
    snapshot_today_stock(db, business)

    bounds = list(db.daily_metrics.aggregate([
        {"$match": {"business_id": business.id}},
        {"$group": {"_id": None, "min": {"$min": "$day"}, "max": {"$max": "$day"}}},
    ]))
    if not bounds:
        return {"available": False, "note": "No history yet — the time machine needs recorded days."}
    d_min, d_max = bounds[0]["min"].date(), bounds[0]["max"].date()
    on_date = min(max(on_date, d_min), d_max)

    rows90 = _window(db, business.id, on_date, 90)
    rows60 = [r for r in rows90 if r.day > on_date - timedelta(days=60)]
    rows30 = [r for r in rows90 if r.day > on_date - timedelta(days=30)]
    prev30 = [r for r in rows90 if on_date - timedelta(days=60) < r.day <= on_date - timedelta(days=30)]

    def _sum(rows: list[DailyMetric], attr: str) -> float:
        return float(sum(getattr(r, attr) for r in rows))

    rev, prev_rev = _sum(rows30, "revenue"), _sum(prev30, "revenue") or 1
    exp, prev_exp = _sum(rows30, "expenses"), _sum(prev30, "expenses") or 1
    cust, prev_cust = _sum(rows30, "customers"), _sum(prev30, "customers") or 1
    the_day = next((r for r in rows90 if r.day == on_date), None)

    # cash curve: cumulative net over the trailing 60 days
    cumulative, cash_curve = 0.0, []
    for r in rows60:
        cumulative += r.revenue - r.expenses
        cash_curve.append({"day": r.day.isoformat(), "net": round(r.revenue - r.expenses),
                           "cumulative": round(cumulative)})

    # top products in the trailing 14 days (sales history covers ~120 days)
    since = to_dt(on_date - timedelta(days=13))
    sales_window = find_models(db, ProductSale, {
        "business_id": business.id, "day": {"$gte": since, "$lte": to_dt(on_date)}})
    name_of = {p.id: p.name for p in _business_products(db, business.id)}
    agg: dict[str, dict] = {}
    for s in sales_window:
        a = agg.setdefault(s.product_id, {"units": 0, "revenue": 0.0})
        a["units"] += s.units
        a["revenue"] += s.revenue
    top_products = sorted(
        ({"name": name_of.get(pid, "Unknown"), **v} for pid, v in agg.items()),
        key=lambda x: -x["revenue"])[:6]

    # events need broader product-sales context for baselines
    sales90 = find_models(db, ProductSale, {
        "business_id": business.id,
        "day": {"$gte": to_dt(on_date - timedelta(days=89)), "$lte": to_dt(on_date)}})
    events = _detect_events(rows90, sales90, on_date - timedelta(days=29), on_date, name_of)

    # archived shelf snapshot for that exact day, when one exists
    snap = db.stock_snapshots.find_one({"business_id": business.id, "day": to_dt(on_date)})

    fest = _festival_near(on_date)
    return {
        "available": True,
        "date": on_date.isoformat(),
        "weekday": WEEKDAYS[on_date.weekday()],
        "range": {"min": d_min.isoformat(), "max": d_max.isoformat()},
        "festival": fest[0] if fest else None,
        "day": ({"revenue": the_day.revenue, "expenses": the_day.expenses,
                 "customers": the_day.customers, "orders": the_day.orders,
                 "inventory_value": the_day.inventory_value} if the_day else None),
        "kpis30": {
            "revenue": round(rev), "expenses": round(exp), "profit": round(rev - exp),
            "customers": int(cust),
            "revenue_change_pct": round((rev / prev_rev - 1) * 100, 1),
            "expense_change_pct": round((exp / prev_exp - 1) * 100, 1),
            "customer_change_pct": round((cust / prev_cust - 1) * 100, 1),
        },
        "trend": [{"day": r.day.isoformat(), "revenue": r.revenue, "expenses": r.expenses,
                   "customers": r.customers} for r in rows60],
        "cash_curve": cash_curve,
        "top_products": top_products,
        "events": events,
        "stock_snapshot": ({"products": snap["products"]} if snap else None),
        "note": ("Replayed from your twin's recorded history. Explanations are inferred "
                 "deterministically — every event shows its evidence."),
    }
