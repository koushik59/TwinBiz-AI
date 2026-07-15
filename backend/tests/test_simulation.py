"""Critical-path tests for the twin simulation engine (deterministic, no DB)."""

from app.services.simulation import (Baseline, Levers, product_price_simulation, simulate)

BASE = Baseline(monthly_revenue=900000, monthly_expenses=700000, monthly_customers=2600,
                employees=8, inventory_value=160000, business_type="Supermarket")


def test_zero_levers_is_neutral():
    r = simulate(BASE, Levers())
    assert r["deltas"] == {"revenue_pct": 0.0, "profit_pct": 0.0,
                           "expenses_pct": 0.0, "customers_pct": 0.0}


def test_deterministic():
    a = simulate(BASE, Levers(price_change_pct=7, marketing_change_pct=30))
    b = simulate(BASE, Levers(price_change_pct=7, marketing_change_pct=30))
    assert a == b


def test_price_increase_cuts_demand():
    r = simulate(BASE, Levers(price_change_pct=10))
    assert r["demand_multiplier"] < 1.0
    assert r["satisfaction"] < simulate(BASE, Levers())["satisfaction"]


def test_discount_boosts_demand_but_costs_margin():
    zero = simulate(BASE, Levers())
    r = simulate(BASE, Levers(discount_pct=15))
    assert r["demand_multiplier"] > 1.0
    assert r["revenue"] / r["demand_multiplier"] < zero["revenue"]  # per-demand revenue falls


def test_marketing_has_diminishing_returns():
    up50 = simulate(BASE, Levers(marketing_change_pct=50))["demand_multiplier"] - 1
    up200 = simulate(BASE, Levers(marketing_change_pct=200))["demand_multiplier"] - 1
    assert up200 < up50 * 4  # far less than linear


def test_hiring_adds_cost_and_capacity():
    r = simulate(BASE, Levers(employee_delta=2))
    zero = simulate(BASE, Levers())
    assert r["expenses"] > zero["expenses"]
    assert r["demand_multiplier"] > 1.0


def test_product_price_headline_case():
    """The pitch demo: milk ₹28 → ₹30 must cut demand mid-single-digits and lift profit."""
    r = product_price_simulation(
        name="Amul Milk 500ml", category="Dairy", current_price=28, cost=24,
        new_price=30, units_per_day=20, stock=200, lead_time_days=2, history_days=120)
    assert -9 < r["delta"]["demand_pct"] < -3
    assert r["delta"]["gross_profit"] > 0
    assert r["confidence_pct"] > 60
    assert r["assumptions"] and r["label"].startswith("Predicted")


def test_product_price_never_guaranteed_label():
    r = product_price_simulation(name="X", category="Snacks", current_price=100, cost=70,
                                 new_price=90, units_per_day=5, stock=50)
    assert "guaranteed" in r["label"]
