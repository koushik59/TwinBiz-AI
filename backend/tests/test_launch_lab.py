"""Launch Lab engine tests on an in-memory twin."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Business, Product, ProductExperiment, ProductSale, User
from app.services import launch_lab


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def twin(db):
    user = User(email="t@t.t", full_name="T", password_hash="x")
    db.add(user)
    db.flush()
    biz = Business(owner_id=user.id, name="Test Mart", monthly_revenue=900000,
                   monthly_expenses=700000, customer_count=2600)
    db.add(biz)
    db.flush()
    for name, price, cost, dd in [("Amul Milk 500ml", 28, 24, 20), ("Amul Butter", 60, 52, 6),
                                  ("Regular Lassi 200ml", 25, 19, 9), ("Eggs", 84, 66, 8)]:
        db.add(Product(business_id=biz.id, name=name, category="Dairy",
                       price=price, cost=cost, stock=150, daily_demand=dd))
    db.flush()
    return biz


@pytest.fixture()
def experiment(db, twin):
    e = ProductExperiment(
        business_id=twin.id, product_name="Amul Protein Lassi 200ml", category="Dairy",
        supplier_cost=25, transport_cost=1, wastage_percent=3,
        min_price=30, max_price=50, price_step=2, planned_price=40,
        discount_percent=10, initial_stock=200, safety_stock=30, reorder_point=70,
        supplier_lead_time=3, marketing_budget=5000, target_segment="Young Adults",
        shelf_placement="Refrigerated Section", competitor_price=45)
    db.add(e)
    db.flush()
    return e


def test_landed_cost_includes_wastage(experiment):
    assert launch_lab.landed_cost(experiment) == pytest.approx(26 / 0.97, abs=0.01)


def test_price_sweep_has_all_points_and_recs(db, twin, experiment):
    r = launch_lab.price_sweep(db, twin, experiment)
    assert len(r["points"]) == 11  # 30..50 step 2
    assert set(r["recommendations"]) == {"best_profit", "best_revenue", "best_adoption",
                                         "balanced", "lowest_risk"}
    # adoption always favours the cheapest price; profit must NOT blindly pick the max price
    assert r["recommendations"]["best_adoption"]["price"] == 30
    assert r["recommendations"]["best_profit"]["price"] < 50
    assert r["assumptions"]


def test_demand_decreases_with_price(db, twin, experiment):
    pts = launch_lab.price_sweep(db, twin, experiment)["points"]
    demands = [p["predicted_demand_month"] for p in pts]
    assert demands == sorted(demands, reverse=True)


def test_sweep_is_deterministic(db, twin, experiment):
    a = launch_lab.price_sweep(db, twin, experiment)["points"]
    b = launch_lab.price_sweep(db, twin, experiment)["points"]
    assert a == b


def test_optimizer_respects_margin_floor(db, twin, experiment):
    r = launch_lab.optimize(db, twin, experiment, min_margin_pct=20)
    for s in r["strategies"].values():
        assert s["margin_pct"] >= 20


def test_optimizer_respects_constraints(db, twin, experiment):
    r = launch_lab.optimize(db, twin, experiment, max_discount=5, max_stock=150,
                            max_marketing=1000, min_margin_pct=5)
    for s in r["strategies"].values():
        assert s["discount_pct"] <= 5
        assert s["stock"] <= 150
        assert s["marketing"] <= 1000


def test_cannibalization_finds_regular_lassi(db, twin, experiment):
    point = launch_lab.simulate_point(db, twin, experiment, price=40)
    c = launch_lab.cannibalization(db, twin, experiment, point)
    names = [v["product"] for v in c["affected_products"]]
    assert "Regular Lassi 200ml" in names
    assert c["net_category_growth_units"] < c["new_product_units"]


def test_risk_score_bounded(db, twin, experiment):
    p = launch_lab.simulate_point(db, twin, experiment, price=40)
    assert 0 <= p["risk_score"] <= 100
    assert p["risk_level"] in {"Low", "Moderate", "High", "Critical"}
    assert 0 <= p["confidence_pct"] <= 100


def test_stock_caps_sales(db, twin, experiment):
    small = launch_lab.simulate_point(db, twin, experiment, price=32, stock=30)
    assert small["predicted_units_sold"] == 30
    assert small["lost_sales_units"] > 0
