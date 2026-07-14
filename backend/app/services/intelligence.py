"""Business intelligence layer: DNA scanner, mood, weather forecast,
opportunity radar and future-news generation.

Everything here is derived deterministically from the twin's real history —
each output carries the evidence it was computed from. No random numbers.
"""

from datetime import date, timedelta

import numpy as np
from pymongo.database import Database

from ..models import Business, DailyMetric, Product, ProductSale, find_models, to_dt
from .forecasting import forecast_series, restock_predictions
from .insights import _business_products, _recent_metrics, detect_risks, health_score

# (month, day, name, span_days) — Indian retail demand calendar
FESTIVALS = [
    (1, 14, "Makar Sankranti", 2), (3, 25, "Holi", 2), (8, 15, "Independence Day", 1),
    (9, 7, "Ganesh Chaturthi", 3), (10, 2, "Gandhi Jayanti", 1), (10, 22, "Dussehra", 5),
    (11, 12, "Diwali", 5), (12, 25, "Christmas", 3),
]

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _trend_pct_per_month(values: list[float]) -> float:
    """Linear-fit slope expressed as % of the mean per 30 days."""
    if len(values) < 14:
        return 0.0
    arr = np.array(values, dtype=float)
    slope = np.polyfit(np.arange(len(arr)), arr, 1)[0]
    return float(slope * 30 / max(arr.mean(), 1) * 100)


# ---------------------------------------------------------------------------
# Business DNA + Mood
# ---------------------------------------------------------------------------

def business_dna(db: Database, business: Business) -> dict:
    rows = _recent_metrics(db, business.id, 180)
    products = _business_products(db, business.id)
    last30 = rows[-30:]

    revs = [r.revenue for r in rows]
    trend = _trend_pct_per_month(revs)
    rev30 = sum(r.revenue for r in last30)
    exp30 = sum(r.expenses for r in last30)
    margin = (rev30 - exp30) / rev30 * 100 if rev30 else 0.0

    traits: list[dict] = []

    def add(key: str, title: str, label: str, score: float, evidence: str):
        traits.append({"key": key, "title": title, "label": label,
                       "score": round(max(0.0, min(100.0, score)), 0), "evidence": evidence})

    # Growth character
    g_label = ("Fast Growth" if trend > 4 else "Growing" if trend > 1
               else "Steady" if trend > -1 else "Declining")
    add("growth", "Growth Character", g_label, 50 + trend * 6,
        f"Revenue trend of {trend:+.1f}%/month over the last {len(rows)} days of history.")

    # Demand stability (coefficient of variation of daily revenue)
    if revs:
        cv = float(np.std(revs) / max(np.mean(revs), 1))
        s_label = "High" if cv < 0.18 else "Medium" if cv < 0.32 else "Volatile"
        add("stability", "Demand Stability", s_label, 100 - cv * 200,
            f"Day-to-day revenue varies ±{cv * 100:.0f}% around its average.")

    # Inventory efficiency (share of products in the healthy stock band)
    if products:
        healthy = sum(1 for p in products if p.daily_demand * 5 <= p.stock <= p.daily_demand * 45)
        eff = healthy / len(products) * 100
        add("inventory", "Inventory Efficiency", f"{eff:.0f}%", eff,
            f"{healthy} of {len(products)} products sit in the healthy 5–45 days-of-demand band.")

    # Customer loyalty (returning share of visits)
    total_c = sum(r.customers for r in last30)
    new_c = sum(r.new_customers for r in last30)
    if total_c:
        retention = (1 - new_c / total_c) * 100
        l_label = ("Very Strong" if retention > 88 else "Strong" if retention > 75
                   else "Moderate" if retention > 60 else "Weak")
        add("loyalty", "Customer Loyalty", l_label, retention,
            f"{retention:.0f}% of the last 30 days' {total_c:,} visits were returning customers.")

    # Resilience (margin buffer + working capital vs monthly expenses)
    inv_value = sum(p.stock * p.cost for p in products)
    buffer_months = (inv_value + max(rev30 - exp30, 0)) / max(exp30, 1)
    r_label = ("Robust" if margin > 12 and buffer_months > 0.6
               else "Stable" if margin > 5 else "Fragile")
    add("resilience", "Resilience", r_label, margin * 3 + buffer_months * 40,
        f"{margin:.1f}% profit margin with ≈{buffer_months:.1f} months of expenses held as "
        f"working capital (₹{inv_value:,.0f} inventory + last month's profit).")

    # Growth potential (trend + margin headroom − stock-loss drag)
    critical = sum(1 for p in products if p.stock < p.daily_demand * 5)
    potential = 50 + trend * 4 + max(margin - 5, 0) * 1.5 - critical * 4
    p_label = ("Excellent" if potential > 78 else "Good" if potential > 60
               else "Moderate" if potential > 45 else "Constrained")
    add("potential", "Growth Potential", p_label, potential,
        f"Momentum {trend:+.1f}%/mo, margin headroom {margin:.1f}%"
        + (f", but {critical} product(s) near stockout are costing sales." if critical else "."))

    return {
        "traits": traits,
        "mood": business_mood(db, business),
        "history_days": len(rows),
        "label": "Derived from your twin's real history — every trait shows its evidence.",
    }


def business_mood(db: Database, business: Business) -> dict:
    health = health_score(db, business)
    risks = detect_risks(db, business)
    rows = _recent_metrics(db, business.id, 60)
    last30, prev30 = rows[-30:], rows[:-30] or rows[-30:]

    positives, negatives = [], []
    rev, prev_rev = sum(r.revenue for r in last30), sum(r.revenue for r in prev30) or 1
    profit = rev - sum(r.expenses for r in last30)
    if rev > prev_rev * 1.02:
        positives.append(f"Sales rising ({(rev / prev_rev - 1) * 100:+.1f}% vs previous month)")
    elif rev < prev_rev * 0.98:
        negatives.append(f"Sales slipping ({(rev / prev_rev - 1) * 100:+.1f}% vs previous month)")
    if profit > 0:
        positives.append(f"Cash positive (₹{profit:,.0f} profit last 30 days)")
    else:
        negatives.append(f"Cash negative (₹{-profit:,.0f} loss last 30 days)")
    inv_pillar = health["pillars"].get("inventory", 50)
    (positives if inv_pillar >= 60 else negatives).append(
        f"Inventory {'healthy' if inv_pillar >= 60 else 'straining'} (pillar {inv_pillar:.0f}/100)")
    for r in risks[:2]:
        if r["severity"] in ("critical", "high"):
            negatives.append(r["title"])

    critical_count = sum(1 for r in risks if r["severity"] == "critical")
    overall = health["overall"]
    if overall >= 70 and critical_count == 0:
        mood, emoji = "Happy", "😊"
    elif overall >= 55 and critical_count == 0:
        mood, emoji = "Content", "🙂"
    elif overall >= 40 or critical_count <= 1:
        mood, emoji = "Stressed", "😟"
    else:
        mood, emoji = "Struggling", "😰"

    return {"mood": mood, "emoji": emoji, "health": overall,
            "positives": positives[:4], "negatives": negatives[:4]}


# ---------------------------------------------------------------------------
# Business Weather
# ---------------------------------------------------------------------------

_ICONS = {"sunny": "🟢", "partly": "🌤", "cloudy": "🟡", "storm": "🔴"}


def _sky(ratio: float) -> str:
    if ratio >= 1.03:
        return "sunny"
    if ratio >= 0.97:
        return "partly"
    if ratio >= 0.88:
        return "cloudy"
    return "storm"


def business_weather(db: Database, business: Business, days: int = 7) -> dict:
    days = max(3, min(days, 14))
    rows = _recent_metrics(db, business.id, 180)
    if len(rows) < 14:
        return {"days": [], "note": "Not enough history yet — the weather report needs at least 14 days of data."}

    fc = forecast_series([(r.day, r.revenue) for r in rows], days)
    # weekday-matched baseline: mean revenue per weekday over the last 8 weeks
    wd_hist: dict[int, list[float]] = {}
    for r in rows[-56:]:
        wd_hist.setdefault(r.day.weekday(), []).append(r.revenue)
    wd_mean = {wd: float(np.mean(v)) for wd, v in wd_hist.items()}

    avg_daily_exp = float(np.mean([r.expenses for r in rows[-28:]]))
    products = _business_products(db, business.id)
    restock = restock_predictions(products)
    top_demand_ids = {r["product_id"] for r in
                      sorted(restock, key=lambda x: -x["daily_demand"])[:10]}

    out, cumulative = [], 0.0
    severity_rank = {"sunny": 0, "partly": 1, "cloudy": 2, "storm": 3}
    for i, point in enumerate(fc["forecast"][:days]):
        d = date.fromisoformat(point["day"])
        # sales sky: forecast vs same-weekday baseline
        base = wd_mean.get(d.weekday(), float(np.mean([r.revenue for r in rows[-28:]])))
        sales_sky = _sky(point["value"] / max(base, 1))
        # inventory sky: does anything run dry by this day?
        dry = [r for r in restock if r["days_until_stockout"] <= i + 1]
        inv_sky = ("storm" if any(r["product_id"] in top_demand_ids for r in dry)
                   else "cloudy" if dry else "sunny")
        inv_note = (f"{dry[0]['name']} runs out" if dry else "Stock levels healthy")
        # cash sky: projected cumulative net from today
        net = point["value"] - avg_daily_exp
        cumulative += net
        cash_sky = "storm" if cumulative < 0 else "cloudy" if net < 0 else "sunny"

        overall = max((sales_sky, inv_sky, cash_sky), key=lambda s: severity_rank[s])
        out.append({
            "day": point["day"],
            "weekday": WEEKDAYS[d.weekday()],
            "overall": overall, "overall_icon": _ICONS[overall],
            "sales": {"sky": sales_sky, "icon": _ICONS[sales_sky],
                      "note": f"₹{point['value']:,.0f} predicted vs ₹{base:,.0f} typical {WEEKDAYS[d.weekday()]}"},
            "inventory": {"sky": inv_sky, "icon": _ICONS[inv_sky], "note": inv_note},
            "cash": {"sky": cash_sky, "icon": _ICONS[cash_sky],
                     "note": f"₹{net:+,.0f} projected net for the day"},
        })
    return {
        "days": out,
        "model_confidence_pct": fc["confidence"],
        "note": "Sales from the ML forecast vs weekday-typical baselines; inventory from live "
                "days-to-stockout; cash from projected daily net. Predicted, not guaranteed.",
    }


# ---------------------------------------------------------------------------
# Opportunity Radar
# ---------------------------------------------------------------------------

def _measured_festival_boost(rows: list[DailyMetric], month: int, day: int, span: int) -> float | None:
    """Measure last occurrence's actual revenue lift vs its surrounding baseline."""
    by_day = {r.day: r.revenue for r in rows}
    for year_offset in (0, 1):
        peak = date(date.today().year - year_offset, month, day)
        if peak >= date.today():
            continue
        window = [by_day[peak + timedelta(days=o)] for o in range(-span, span + 1)
                  if peak + timedelta(days=o) in by_day]
        baseline = [by_day[peak + timedelta(days=o)] for o in
                    list(range(-span - 15, -span)) + list(range(span + 1, span + 16))
                    if peak + timedelta(days=o) in by_day]
        if len(window) >= span and len(baseline) >= 10:
            return float(np.mean(window) / max(np.mean(baseline), 1) - 1)
    return None


def opportunity_radar(db: Database, business: Business) -> dict:
    rows = _recent_metrics(db, business.id, 400)
    products = _business_products(db, business.id)
    last30 = rows[-30:]
    daily_rev = float(np.mean([r.revenue for r in last30])) if last30 else 0.0
    opportunities: list[dict] = []

    # 1. Upcoming festival demand windows, sized from last year's measured lift
    today = date.today()
    for month, day, name, span in FESTIVALS:
        peak = date(today.year, month, day)
        if peak < today:
            peak = date(today.year + 1, month, day)
        days_away = (peak - today).days
        if not 0 <= days_away <= 60:
            continue
        measured = _measured_festival_boost(rows, month, day, span)
        boost = measured if measured is not None else 0.25
        extra = daily_rev * boost * (span * 2 + 1)
        top = sorted(products, key=lambda p: -(p.daily_demand * p.price))[:4]
        opportunities.append({
            "kind": "festival", "title": f"{name} demand window",
            "when": peak.isoformat(), "days_away": days_away,
            "expected_boost_pct": round(boost * 100, 0),
            "expected_extra_revenue": round(max(extra, 0), 0),
            "suggested_products": [p.name for p in top],
            "evidence": (f"Measured from your own history: the last {name} window averaged "
                         f"{boost * 100:+.0f}% vs its surrounding weeks." if measured is not None
                         else "No prior occurrence in your history — using a conservative +25% estimate."),
            "action": f"Stock up your fast movers ~{max(days_away - span - 3, 1)} days ahead and "
                      f"plan a festival offer.",
        })

    # 2. Strongest weekday — capture more of your best day
    if len(rows) >= 60:
        wd: dict[int, list[float]] = {}
        for r in rows[-90:]:
            wd.setdefault(r.day.weekday(), []).append(r.revenue)
        means = {k: float(np.mean(v)) for k, v in wd.items()}
        overall = float(np.mean(list(means.values())))
        best = max(means, key=lambda k: means[k])
        lift = means[best] / max(overall, 1) - 1
        if lift > 0.08:
            opportunities.append({
                "kind": "weekday", "title": f"{WEEKDAYS[best]}s are your power day",
                "when": None, "days_away": None,
                "expected_boost_pct": round(lift * 100, 0),
                "expected_extra_revenue": round(means[best] * 0.15 * 4, 0),
                "suggested_products": [],
                "evidence": f"{WEEKDAYS[best]}s average ₹{means[best]:,.0f} — {lift * 100:.0f}% above "
                            f"your typical day, measured over 90 days.",
                "action": "Schedule full staffing, fresh stock and promotions on this day; "
                          "capturing 15% more of it is the estimate shown.",
            })

    # 3. Rising categories (last 60d vs previous 60d of product sales)
    since = to_dt(today - timedelta(days=120))
    sales = find_models(db, ProductSale, {"business_id": business.id, "day": {"$gte": since}})
    if sales:
        cat_of = {p.id: p.category for p in products}
        halves: dict[str, list[float]] = {}
        mid = today - timedelta(days=60)
        for s in sales:
            cat = cat_of.get(s.product_id)
            if not cat:
                continue
            halves.setdefault(cat, [0.0, 0.0])
            halves[cat][1 if s.day >= mid else 0] += s.revenue
        for cat, (old, new) in sorted(halves.items(), key=lambda kv: -(kv[1][1] - kv[1][0])):
            if old > 0 and new > old * 1.15:
                growth = (new / old - 1) * 100
                opportunities.append({
                    "kind": "category", "title": f"{cat} is trending up",
                    "when": None, "days_away": None,
                    "expected_boost_pct": round(growth, 0),
                    "expected_extra_revenue": round((new - old) / 2, 0),
                    "suggested_products": [p.name for p in products if p.category == cat][:4],
                    "evidence": f"{cat} sales grew {growth:.0f}% in the last 60 days vs the 60 before "
                                f"(₹{new:,.0f} vs ₹{old:,.0f}).",
                    "action": "Widen the range and deepen stock in this category while momentum holds.",
                })
                break  # top rising category only

    # 4. Clearance: free capital locked in slow movers
    over = [p for p in products if p.daily_demand > 0 and p.stock > p.daily_demand * 60]
    if over:
        capital = sum(p.stock * p.cost for p in over)
        opportunities.append({
            "kind": "clearance", "title": f"₹{capital:,.0f} locked in {len(over)} slow mover(s)",
            "when": None, "days_away": None,
            "expected_boost_pct": None, "expected_extra_revenue": round(capital * 0.6, 0),
            "suggested_products": [p.name for p in sorted(over, key=lambda p: -p.stock * p.cost)[:4]],
            "evidence": "These products hold more than 60 days of demand in stock.",
            "action": "A 10–15% clearance offer converts dead stock back into working capital "
                      "for fast movers (estimate shown is ~60% recovery).",
        })

    opportunities.sort(key=lambda o: -(o["expected_extra_revenue"] or 0))
    return {"opportunities": opportunities,
            "label": "Detected from your seasonality calendar and measured sales trends."}


# ---------------------------------------------------------------------------
# Future News Generator
# ---------------------------------------------------------------------------

def future_news(db: Database, business: Business) -> dict:
    rows = _recent_metrics(db, business.id, 180)
    products = _business_products(db, business.id)
    headlines: list[dict] = []
    today = date.today()

    fc = forecast_series([(r.day, r.revenue) for r in rows], 90) if len(rows) >= 14 else {"forecast": []}
    trend = fc.get("trend_pct_per_month", 0)

    def add(when: date, tone: str, headline: str, story: str, based_on: str):
        headlines.append({"date": when.isoformat(), "dateline": when.strftime("%B %Y"),
                          "tone": tone, "headline": headline, "story": story, "based_on": based_on})

    # Trajectory headline (3 months out)
    if fc["forecast"]:
        in90 = today + timedelta(days=90)
        q_rev = sum(p["value"] for p in fc["forecast"])
        if trend >= 1.5:
            add(in90, "good", f"{business.name} Reports {trend * 3:.0f}% Quarterly Growth",
                f"Staying on its current trajectory, the store closes the quarter near "
                f"₹{q_rev:,.0f} in revenue — up {trend:+.1f}% each month.",
                f"90-day ML forecast (model confidence {fc.get('confidence', 0):.0f}%)")
        elif trend <= -1.5:
            add(in90, "bad", f"{business.name} Faces Third Straight Month of Falling Sales",
                f"If the current {trend:+.1f}%/month slide continues, quarterly revenue lands near "
                f"₹{q_rev:,.0f}. The simulator's marketing and pricing levers can rewrite this headline.",
                f"90-day ML forecast (model confidence {fc.get('confidence', 0):.0f}%)")
        else:
            add(in90, "neutral", f"{business.name} Holds Steady Through the Quarter",
                f"Revenue is projected flat at ≈₹{q_rev / 3:,.0f}/month. Steady is safe — "
                f"but the Opportunity Radar lists ways to bend this curve upward.",
                "90-day ML forecast")

    # Stockout-before-festival headline
    restock = restock_predictions(products)
    critical = [r for r in restock if r["status"] in ("critical", "low")]
    next_fest = None
    for month, day, name, span in FESTIVALS:
        peak = date(today.year, month, day)
        if peak < today:
            peak = date(today.year + 1, month, day)
        if next_fest is None or peak < next_fest[0]:
            next_fest = (peak, name)
    if critical:
        first = critical[0]
        dry_date = today + timedelta(days=int(first["days_until_stockout"]))
        if next_fest and abs((next_fest[0] - dry_date).days) <= 21:
            add(next_fest[0], "bad",
                f"Store Faces Stockouts During {next_fest[1]} Rush",
                f"{first['name']} runs dry around {dry_date.strftime('%d %b')} — right before "
                f"{next_fest[1]}. {len(critical)} product(s) need reordering to save the "
                f"season's busiest days.",
                f"Live days-to-stockout: {first['name']} has {first['days_until_stockout']:.0f} days left")
        else:
            add(dry_date, "warn",
                f"Shoppers Find Empty Shelves as {first['name']} Sells Out",
                f"At current demand ({first['daily_demand']}/day), {first['name']} is gone in "
                f"{first['days_until_stockout']:.0f} days. A ₹{first['suggested_order'] * 1:,.0f}-unit "
                f"reorder rewrites this story.",
                "Live inventory velocity")

    # Margin/pricing headline
    last30 = rows[-30:]
    rev30 = sum(r.revenue for r in last30)
    margin = (rev30 - sum(r.expenses for r in last30)) / rev30 * 100 if rev30 else 0
    if margin > 14:
        add(today + timedelta(days=365), "good",
            f"{business.name} Posts Record Profit After Strategic Pricing Decision",
            f"With a healthy {margin:.1f}% margin today, a tested 3–5% price move on "
            f"low-elasticity categories compounds into a standout year.",
            f"Current margin {margin:.1f}% + category elasticity model")
    elif margin < 5:
        add(today + timedelta(days=180), "bad",
            "Thin Margins Leave No Room for a Bad Month",
            f"At {margin:.1f}% margin, one weak season erases the year's profit. Supplier "
            f"renegotiation and the stress-test playbook are this story's escape hatch.",
            f"Current margin {margin:.1f}%")

    return {
        "headlines": headlines[:5],
        "label": "Illustrative projections written from your real forecast, inventory and margin "
                 "numbers — these are simulations, not guarantees.",
    }
