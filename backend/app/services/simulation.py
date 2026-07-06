"""TwinBiz simulation engine.

Economics-grounded what-if model: each lever (price, marketing, staffing, ...)
perturbs demand, revenue, cost and satisfaction through elasticity curves
calibrated to the business's real historical baseline.
"""

import math
from dataclasses import dataclass, field


# Price elasticity of demand by business type (how sharply demand reacts to price)
PRICE_ELASTICITY = {
    "Supermarket": -1.8, "Retail": -1.5, "Restaurant": -1.2, "Pharmacy": -0.6,
    "Salon": -1.0, "Bakery": -1.4, "Warehouse": -0.9, "Manufacturing": -0.8,
    "Education": -0.5,
}

# Diminishing-returns strength of marketing by type
MARKETING_RESPONSE = {
    "Supermarket": 0.12, "Retail": 0.16, "Restaurant": 0.18, "Pharmacy": 0.07,
    "Salon": 0.20, "Bakery": 0.15, "Warehouse": 0.05, "Manufacturing": 0.06,
    "Education": 0.14,
}


@dataclass
class Levers:
    """Simulator inputs, expressed as % change from current state (except absolutes)."""

    price_change_pct: float = 0.0        # -30 .. +30
    marketing_change_pct: float = 0.0    # -50 .. +200
    employee_delta: int = 0              # -5 .. +10
    discount_pct: float = 0.0            # 0 .. 40
    inventory_change_pct: float = 0.0    # -50 .. +100
    hours_delta: float = 0.0             # -4 .. +6 (hours/day)
    supplier_cost_change_pct: float = 0.0  # -20 .. +20
    opex_change_pct: float = 0.0         # -30 .. +30


@dataclass
class Baseline:
    monthly_revenue: float
    monthly_expenses: float
    monthly_customers: int
    employees: int
    inventory_value: float
    business_type: str = "Supermarket"
    marketing_budget: float = field(default=0.0)

    def __post_init__(self):
        if not self.marketing_budget:
            # assume ~5% of expenses goes to marketing if unknown
            self.marketing_budget = 0.05 * self.monthly_expenses


def _saturating(x: float, scale: float) -> float:
    """Diminishing-returns curve: returns multiplier-delta for input fraction x."""
    return scale * math.tanh(x)


def simulate(base: Baseline, levers: Levers) -> dict:
    btype = base.business_type if base.business_type in PRICE_ELASTICITY else "Retail"
    elasticity = PRICE_ELASTICITY[btype]
    mkt_response = MARKETING_RESPONSE[btype]

    # --- demand multiplier -------------------------------------------------
    price_frac = levers.price_change_pct / 100.0
    demand_mult = (1 + price_frac) ** elasticity if price_frac > -1 else 2.5

    # discounts behave like a price cut but also attract deal-seekers
    disc_frac = levers.discount_pct / 100.0
    demand_mult *= (1 - disc_frac) ** (elasticity * 0.8)

    # marketing with diminishing returns
    mkt_frac = levers.marketing_change_pct / 100.0
    demand_mult *= 1 + _saturating(mkt_frac, mkt_response) * 2.2

    # staffing affects service capacity & wait times
    per_emp = 1.0 / max(base.employees, 1)
    staff_frac = levers.employee_delta * per_emp
    demand_mult *= 1 + _saturating(staff_frac, 0.10) * 1.6

    # longer hours capture marginal demand (~2.5%/hour, saturating)
    demand_mult *= 1 + _saturating(levers.hours_delta / 8.0, 0.11)

    # stockouts throttle demand if inventory shrinks hard
    inv_frac = levers.inventory_change_pct / 100.0
    if inv_frac < -0.15:
        demand_mult *= 1 + (inv_frac + 0.15) * 0.5  # lost sales

    # --- revenue ------------------------------------------------------------
    effective_price_mult = (1 + price_frac) * (1 - disc_frac)
    revenue = base.monthly_revenue * demand_mult * effective_price_mult

    # --- expenses -----------------------------------------------------------
    avg_salary = 18000.0
    cogs_share = 0.55  # supplier-driven share of expenses
    opex_share = 1 - cogs_share - 0.05  # rest minus marketing share
    cogs = base.monthly_expenses * cogs_share * demand_mult * (1 + levers.supplier_cost_change_pct / 100.0)
    marketing = base.marketing_budget * (1 + mkt_frac)
    opex = base.monthly_expenses * opex_share * (1 + levers.opex_change_pct / 100.0)
    opex *= 1 + max(levers.hours_delta, 0) * 0.015  # utilities etc. for longer hours
    payroll_delta = levers.employee_delta * avg_salary
    inventory_carry = base.inventory_value * 0.02 * (1 + inv_frac)
    expenses = cogs + marketing + opex + payroll_delta + inventory_carry

    profit = revenue - expenses
    base_profit = base.monthly_revenue - base.monthly_expenses

    # --- customers & satisfaction --------------------------------------------
    customers = int(base.monthly_customers * demand_mult)
    satisfaction = 72.0
    satisfaction -= price_frac * 40           # price hikes hurt
    satisfaction += disc_frac * 25            # deals delight
    satisfaction += _saturating(staff_frac, 0.10) * 90  # faster service
    satisfaction += min(levers.hours_delta, 0) * 1.5    # shorter hours annoy
    if inv_frac < -0.15:
        satisfaction += (inv_frac + 0.15) * 30          # stockouts frustrate
    satisfaction = max(5.0, min(98.0, satisfaction))

    churn_risk = max(2.0, min(95.0, 20 - (satisfaction - 72) * 1.2 + max(price_frac, 0) * 60))

    # --- cash flow & inventory ------------------------------------------------
    inventory_value = base.inventory_value * (1 + inv_frac)
    inventory_purchase_cash = base.inventory_value * inv_frac  # one-off cash out
    cash_flow = profit - inventory_purchase_cash
    inventory_days = 30 * inventory_value / max(cogs, 1)

    # --- health & risk ----------------------------------------------------------
    margin = profit / revenue if revenue > 0 else -1
    health = 50.0
    health += min(margin, 0.35) * 100
    health += (satisfaction - 72) * 0.35
    health += 8 if cash_flow > 0 else -14
    if 15 <= inventory_days <= 60:
        health += 6
    else:
        health -= 6
    health = max(5.0, min(98.0, health))

    risk = 25.0
    risk += max(price_frac, 0) * 55 + max(-inv_frac - 0.15, 0) * 60
    risk += 18 if cash_flow < 0 else 0
    risk += 15 if profit < base_profit * 0.75 else 0
    risk += abs(levers.employee_delta) * 1.5
    risk = max(3.0, min(97.0, risk))

    result = {
        "revenue": round(revenue, 0),
        "expenses": round(expenses, 0),
        "profit": round(profit, 0),
        "profit_margin_pct": round(margin * 100, 1),
        "customers": customers,
        "customer_change_pct": round((demand_mult - 1) * 100, 1),
        "satisfaction": round(satisfaction, 1),
        "churn_risk_pct": round(churn_risk, 1),
        "demand_multiplier": round(demand_mult, 3),
        "cash_flow": round(cash_flow, 0),
        "inventory_value": round(inventory_value, 0),
        "inventory_days": round(inventory_days, 1),
        "health_score": round(health, 1),
        "risk_score": round(risk, 1),
    }
    # deltas vs the zero-lever twin state, so an untouched simulator reads exactly 0%
    if levers == Levers():
        result["deltas"] = {"revenue_pct": 0.0, "profit_pct": 0.0, "expenses_pct": 0.0, "customers_pct": 0.0}
    else:
        zero = simulate(base, Levers())
        result["deltas"] = {
            "revenue_pct": round((revenue / zero["revenue"] - 1) * 100, 1) if zero["revenue"] else 0.0,
            "profit_pct": round((profit / zero["profit"] - 1) * 100, 1) if zero["profit"] else 0.0,
            "expenses_pct": round((expenses / zero["expenses"] - 1) * 100, 1) if zero["expenses"] else 0.0,
            "customers_pct": round((demand_mult - 1) * 100, 1),
        }
    return result


# Named what-if presets exposed in the UI
WHAT_IF_PRESETS: dict[str, Levers] = {
    "increase_price_10": Levers(price_change_pct=10),
    "decrease_price_10": Levers(price_change_pct=-10),
    "hire_2_employees": Levers(employee_delta=2),
    "reduce_1_employee": Levers(employee_delta=-1),
    "festival_offer": Levers(discount_pct=15, marketing_change_pct=60, inventory_change_pct=25),
    "double_marketing": Levers(marketing_change_pct=100),
    "reduce_inventory_20": Levers(inventory_change_pct=-20),
    "cheaper_supplier": Levers(supplier_cost_change_pct=-8),
    "extend_hours_2": Levers(hours_delta=2),
    "cut_opex_15": Levers(opex_change_pct=-15),
}
