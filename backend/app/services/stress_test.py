"""Business Stress Test Simulator: banking-style shock scenarios on the twin.

Uses the same expense decomposition as the main simulation engine
(COGS 55% of expenses, marketing 5%, rest opex) plus explicit demand shocks,
so every scenario is deterministic and its assumptions are surfaced.
"""

import math
from dataclasses import dataclass

from pymongo.database import Database

from ..models import Business
from .insights import _business_products, _recent_metrics

COGS_SHARE = 0.55
AVG_SALARY = 18000.0


@dataclass
class Shock:
    key: str
    title: str
    description: str
    demand_pct: float = 0.0          # demand shock (customers/units)
    price_pct: float = 0.0           # forced selling-price move
    supplier_cost_pct: float = 0.0   # COGS inflation
    opex_pct: float = 0.0            # operating-cost inflation
    staff_out_pct: float = 0.0       # share of workforce unavailable
    supply_cut_pct: float = 0.0      # share of replenishment that fails to arrive
    assumptions: tuple[str, ...] = ()


SCENARIOS: list[Shock] = [
    Shock("supplier_delay", "40% Supplier Delay",
          "Your suppliers deliver only 60% of orders on time for a month.",
          supply_cut_pct=40, supplier_cost_pct=3,
          assumptions=("Lost sales rise once shelf stock cannot cover demand",
                       "Expedited partial deliveries add ~3% to supplier cost")),
    Shock("staff_absence", "25% Employee Absence",
          "A quarter of your team is out (illness, exits) for a month.",
          staff_out_pct=25,
          assumptions=("Service capacity falls with headcount; some customers walk out",
                       "Payroll saving from absent staff partially offsets the revenue hit")),
    Shock("inflation", "15% Cost Inflation",
          "Supplier prices rise 15% and operating costs 8%; you hold retail prices.",
          supplier_cost_pct=15, opex_pct=8,
          assumptions=("Retail prices held constant — the margin absorbs the shock",
                       "Passing costs to customers is the tested recovery lever")),
    Shock("fuel_spike", "Fuel Price Surge",
          "Transport-driven costs jump: +6% on goods, +4% on operations.",
          supplier_cost_pct=6, opex_pct=4,
          assumptions=("Fuel feeds both inbound logistics (COGS) and utilities/delivery (opex)",)),
    Shock("demand_collapse", "Pandemic-style Demand Shock",
          "Footfall collapses 35% for the month while fixed costs continue.",
          demand_pct=-35,
          assumptions=("Variable costs (COGS) fall with demand; payroll, rent and opex do not",)),
    Shock("festival_rush", "Festival Rush (+60% demand)",
          "A festival week multiplies demand — can your stock and staff serve it?",
          demand_pct=60,
          assumptions=("Sales are capped by current stock cover — demand beyond it is lost",
                       "Staff strain lowers satisfaction at peak load")),
]


def run_scenario(db: Database, business: Business, shock: Shock) -> dict:
    rows = _recent_metrics(db, business.id, 30)
    products = _business_products(db, business.id)

    base_rev = sum(r.revenue for r in rows) or business.monthly_revenue
    base_exp = sum(r.expenses for r in rows) or business.monthly_expenses
    base_profit = base_rev - base_exp
    inv_value = sum(p.stock * p.cost for p in products)
    employees = max(business.employees_count, 1)

    # --- demand under the shock -------------------------------------------
    demand_mult = 1 + shock.demand_pct / 100.0
    # staffing shortfall throttles service capacity (same tanh family as the simulator,
    # where staff_frac = headcount change / headcount = -staff_out_pct)
    if shock.staff_out_pct:
        demand_mult *= 1 + 0.10 * math.tanh(-shock.staff_out_pct / 100.0) * 1.6
        demand_mult *= 1 - shock.staff_out_pct / 100.0 * 0.35  # walkouts at peak times

    # --- stock ceiling: how much of that demand can current stock serve? ---
    avg_days_of_stock = (
        sum(min(p.stock / max(p.daily_demand, 0.1), 90) for p in products) / len(products)
        if products else 30.0
    )
    effective_cover = avg_days_of_stock * (1 - shock.supply_cut_pct / 100.0 * 0.5)
    demanded_days = 30 * demand_mult
    served_frac = min(effective_cover / max(demanded_days, 1), 1.0) if products else 1.0
    # replenishment keeps flowing (partially under supply cuts), so floor the loss
    served_frac = max(served_frac, 0.55 if shock.supply_cut_pct else 0.7)

    revenue = base_rev * demand_mult * served_frac * (1 + shock.price_pct / 100.0)
    lost_sales = base_rev * demand_mult * (1 - served_frac)

    # --- expenses ------------------------------------------------------------
    cogs = base_exp * COGS_SHARE * demand_mult * served_frac * (1 + shock.supplier_cost_pct / 100.0)
    payroll_saving = employees * (shock.staff_out_pct / 100.0) * AVG_SALARY * 0.5
    opex = base_exp * (1 - COGS_SHARE) * (1 + shock.opex_pct / 100.0) - payroll_saving
    expenses = cogs + max(opex, 0)
    profit = revenue - expenses

    # --- survival & stock metrics ---------------------------------------------
    monthly_hit = profit - base_profit
    if profit < 0:
        buffer = inv_value + max(base_profit, 0)
        survival_months = round(buffer / abs(profit), 1)
    else:
        survival_months = None  # profitable under stress
    stock_days = round(effective_cover / max(demand_mult, 0.1), 1)

    # --- recovery playbook (deterministic per scenario) -------------------------
    recovery = {
        "supplier_delay": "Split orders across your two most reliable suppliers, raise reorder "
                          "points by the delay days, and prioritise fast movers for the stock you do receive.",
        "staff_absence": "Cross-train staff on checkout, shorten hours on the two weakest weekdays, "
                         "and hire one temp — the simulator prices this at ~₹18,000/month.",
        "inflation": "Pass 6–8% to customers on low-elasticity categories (Dairy, Staples) and "
                     "renegotiate the top-3 supplier contracts; both are testable in the Simulator.",
        "fuel_spike": "Consolidate deliveries to fewer, fuller orders and shift slow-mover "
                      "replenishment to a slower, cheaper cadence.",
        "demand_collapse": "Cut inventory purchases to essentials, trim opex 10%, and hold prices — "
                           "discounting into a demand collapse destroys margin without recovering volume.",
        "festival_rush": "Pre-build stock 10–14 days ahead on fast movers and add temp staff for "
                         "the window; every unserved rupee here is pure lost profit.",
    }[shock.key]

    return {
        "key": shock.key, "title": shock.title, "description": shock.description,
        "baseline": {"revenue": round(base_rev), "expenses": round(base_exp), "profit": round(base_profit)},
        "stressed": {"revenue": round(revenue), "expenses": round(expenses), "profit": round(profit)},
        "monthly_cash_impact": round(monthly_hit),
        "lost_sales": round(lost_sales),
        "survival_months": survival_months,
        "survives": profit >= 0 or (survival_months or 0) >= 3,
        "stock_days_under_stress": stock_days,
        "served_demand_pct": round(served_frac * 100),
        "recovery_strategy": recovery,
        "assumptions": list(shock.assumptions) + [
            f"COGS assumed at {COGS_SHARE * 100:.0f}% of expenses (same as the simulator)",
            "Survival months = (inventory working capital + one month's profit) ÷ monthly loss",
        ],
        "label": "Predicted (not guaranteed)",
    }


def run_all(db: Database, business: Business) -> dict:
    results = [run_scenario(db, business, s) for s in SCENARIOS]
    failing = [r for r in results if not r["survives"]]
    return {
        "scenarios": results,
        "summary": {
            "tested": len(results),
            "survived": len(results) - len(failing),
            "weakest": min(results, key=lambda r: r["stressed"]["profit"])["title"],
        },
    }
