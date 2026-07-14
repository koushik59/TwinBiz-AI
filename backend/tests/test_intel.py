"""Intelligence-layer engine tests (DNA, weather, stress tests, time machine, CEO)."""

from datetime import date, timedelta

import mongomock
import pytest

from app.models import (Business, DailyMetric, Product, ProductSale, User,
                        insert_model)
from app.services import ceo, stress_test, time_machine
from app.services.intelligence import (business_dna, business_weather, future_news,
                                       opportunity_radar)


@pytest.fixture()
def db():
    return mongomock.MongoClient()["twinbiz_test"]


@pytest.fixture()
def twin(db):
    user = insert_model(db, User(email="i@i.i", full_name="I", password_hash="x"))
    biz = insert_model(db, Business(owner_id=user.id, name="Intel Mart",
                                    employees_count=8, monthly_revenue=900000,
                                    monthly_expenses=700000, customer_count=2600))
    today = date.today()
    metrics, sales = [], []
    products = [
        insert_model(db, Product(business_id=biz.id, name="Amul Milk 500ml", category="Dairy",
                                 price=28, cost=24, stock=140, daily_demand=20)),
        insert_model(db, Product(business_id=biz.id, name="Lays Chips", category="Snacks",
                                 price=20, cost=14, stock=30, daily_demand=15)),   # low stock
        insert_model(db, Product(business_id=biz.id, name="Surf Excel 1kg", category="Household",
                                 price=210, cost=160, stock=900, daily_demand=3)),  # overstock
    ]
    weekday_mult = [0.9, 0.92, 0.95, 1.0, 1.05, 1.2, 1.15]
    for i in range(200):
        d = today - timedelta(days=199 - i)
        growth = 1 + 0.15 * i / 200
        rev = 30000 * weekday_mult[d.weekday()] * growth
        metrics.append(DailyMetric(business_id=biz.id, day=d, revenue=round(rev),
                                   expenses=round(rev * 0.8), customers=90, orders=60,
                                   new_customers=9, inventory_value=150000).to_doc())
        if i >= 100:  # 100 days of product sales
            for p in products:
                # milk goes silent for 5 days, 20 days ago (stockout signature)
                if p.name.startswith("Amul") and 15 <= (today - d).days <= 19:
                    continue
                sales.append(ProductSale(business_id=biz.id, product_id=p.id, day=d,
                                         units=int(p.daily_demand),
                                         revenue=int(p.daily_demand * p.price)).to_doc())
    db.daily_metrics.insert_many(metrics)
    db.product_sales.insert_many(sales)
    return biz


def test_dna_traits_present_and_grounded(db, twin):
    dna = business_dna(db, twin)
    keys = {t["key"] for t in dna["traits"]}
    assert {"growth", "stability", "inventory", "loyalty", "resilience", "potential"} <= keys
    growth = next(t for t in dna["traits"] if t["key"] == "growth")
    assert growth["label"] in ("Fast Growth", "Growing")  # seeded with a rising trend
    for t in dna["traits"]:
        assert 0 <= t["score"] <= 100 and t["evidence"]
    assert dna["mood"]["mood"] in ("Happy", "Content", "Stressed", "Struggling")


def test_weather_returns_days_with_all_layers(db, twin):
    w = business_weather(db, twin, days=7)
    assert len(w["days"]) == 7
    for d in w["days"]:
        assert d["overall"] in ("sunny", "partly", "cloudy", "storm")
        assert d["sales"]["sky"] and d["inventory"]["sky"] and d["cash"]["sky"]
    # Lays (30 stock / 15 per day) runs dry inside the window -> not all-sunny inventory
    assert any(d["inventory"]["sky"] != "sunny" for d in w["days"])


def test_stress_scenarios_all_run_and_are_ordered_sanely(db, twin):
    result = stress_test.run_all(db, twin)
    assert len(result["scenarios"]) == 6
    by_key = {s["key"]: s for s in result["scenarios"]}
    base_profit = by_key["inflation"]["baseline"]["profit"]
    # inflation with held prices must hurt profit
    assert by_key["inflation"]["stressed"]["profit"] < base_profit
    # demand collapse must hurt more than a fuel spike
    assert by_key["demand_collapse"]["stressed"]["profit"] < by_key["fuel_spike"]["stressed"]["profit"]
    for s in result["scenarios"]:
        assert s["recovery_strategy"] and s["assumptions"]
        if s["stressed"]["profit"] < 0:
            assert s["survival_months"] is not None and s["survival_months"] > 0


def test_time_machine_replays_past_date_and_finds_stockout(db, twin):
    on = date.today() - timedelta(days=10)
    r = time_machine.replay(db, twin, on)
    assert r["available"] and r["date"] == on.isoformat()
    assert r["kpis30"]["revenue"] > 0
    assert len(r["trend"]) > 30
    # the seeded 5-day milk silence must surface as a stockout event
    assert any(e["kind"] == "stockout" and "Amul Milk" in e["title"] for e in r["events"])
    # replay clamps out-of-range dates instead of failing
    assert time_machine.replay(db, twin, date(2000, 1, 1))["available"]


def test_time_machine_snapshots_todays_stock(db, twin):
    time_machine.replay(db, twin, date.today())
    snap = db.stock_snapshots.find_one({"business_id": twin.id})
    assert snap and len(snap["products"]) == 3


def test_opportunities_include_clearance_for_overstock(db, twin):
    r = opportunity_radar(db, twin)
    kinds = {o["kind"] for o in r["opportunities"]}
    assert "clearance" in kinds  # Surf Excel is 300 days of stock
    for o in r["opportunities"]:
        assert o["evidence"] and o["action"]


def test_future_news_has_labeled_headlines(db, twin):
    r = future_news(db, twin)
    assert 1 <= len(r["headlines"]) <= 5
    for h in r["headlines"]:
        assert h["tone"] in ("good", "bad", "warn", "neutral")
        assert h["based_on"] and h["dateline"]
    assert "Illustrative" in r["label"]


def test_ceo_proposes_approves_and_applies_price(db, twin):
    out = ceo.list_decisions(db, twin)
    assert out["pending_count"] >= 2  # at least restock (Lays) + clearance or price
    kinds = {d["kind"] for d in out["decisions"]}
    assert "restock" in kinds
    # approving a price decision actually changes the product price
    price_d = next((d for d in out["decisions"] if d["kind"] == "price"), None)
    if price_d:
        old = db.products.find_one({"name": "Amul Milk 500ml"})["price"]
        result = ceo.decide(db, twin, price_d["id"], approve=True)
        assert result["ok"]
        new = db.products.find_one({"name": "Amul Milk 500ml"})["price"]
        assert new != old
    # rejecting stops re-proposal
    restock_d = next(d for d in out["decisions"] if d["kind"] == "restock" and d["status"] == "pending")
    ceo.decide(db, twin, restock_d["id"], approve=False)
    again = ceo.list_decisions(db, twin)
    same_key_pending = [d for d in again["decisions"]
                        if d["title"] == restock_d["title"] and d["status"] == "pending"]
    assert not same_key_pending


def test_ceo_double_decide_is_rejected(db, twin):
    out = ceo.list_decisions(db, twin)
    d = next(d for d in out["decisions"] if d["status"] == "pending")
    assert ceo.decide(db, twin, d["id"], approve=True)["ok"]
    assert not ceo.decide(db, twin, d["id"], approve=True)["ok"]
