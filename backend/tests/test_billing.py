"""Billing engine tests: stock, sales and metrics stay consistent per bill."""

from datetime import date

import mongomock
import pytest

from app.models import Business, Product, User, insert_model, to_dt
from app.services import billing


@pytest.fixture()
def db():
    return mongomock.MongoClient()["twinbiz_test"]


@pytest.fixture()
def twin(db):
    user = insert_model(db, User(email="b@b.b", full_name="B", password_hash="x"))
    return insert_model(db, Business(owner_id=user.id, name="Bill Mart", data_source="demo"))


@pytest.fixture()
def milk(db, twin):
    return insert_model(db, Product(business_id=twin.id, name="Amul Milk 500ml",
                                    price=28, cost=24, stock=100, tax_rate=5.0))


def test_bill_updates_stock_sales_and_metrics(db, twin, milk):
    bill = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 4}],
                               customer_name="Ravi", customer_phone="9876543210",
                               payment_method="upi")
    assert bill.bill_no == "INV-00001"
    assert bill.total == pytest.approx(112.0)
    assert bill.counted_new_customer == 1  # first time this phone was seen

    assert db.products.find_one({"_id": {"$exists": True}})["stock"] == 96
    sale = db.product_sales.find_one({"product_id": milk.id})
    assert sale["units"] == 4 and sale["revenue"] == pytest.approx(112.0)
    metric = db.daily_metrics.find_one({"business_id": twin.id, "day": to_dt(date.today())})
    assert metric["revenue"] == pytest.approx(112.0)
    assert metric["orders"] == 1 and metric["customers"] == 1 and metric["new_customers"] == 1
    assert db.businesses.find_one()["data_source"] == "mixed"  # real data arrived


def test_second_bill_same_phone_is_returning_customer(db, twin, milk):
    billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 1}],
                        customer_phone="9876543210")
    b2 = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 1}],
                             customer_phone="9876543210")
    assert b2.counted_new_customer == 0
    assert b2.bill_no == "INV-00002"


def test_discount_applies_to_totals_and_sales(db, twin, milk):
    bill = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 10}],
                               discount_pct=10)
    assert bill.subtotal == pytest.approx(280.0)
    assert bill.discount_amount == pytest.approx(28.0)
    assert bill.total == pytest.approx(252.0)
    sale = db.product_sales.find_one({"product_id": milk.id})
    assert sale["revenue"] == pytest.approx(252.0)  # net of discount


def test_insufficient_stock_rejected_without_side_effects(db, twin, milk):
    with pytest.raises(billing.BillingError, match="Only 100 units"):
        billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 500}])
    assert db.products.find_one()["stock"] == 100
    assert db.daily_metrics.count_documents({}) == 0


def test_cancel_reverses_everything(db, twin, milk):
    bill = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 4}],
                               customer_phone="9000000001")
    billing.cancel_bill(db, twin, bill)
    assert db.products.find_one()["stock"] == 100
    sale = db.product_sales.find_one({"product_id": milk.id})
    assert sale["units"] == 0 and sale["revenue"] == pytest.approx(0.0)
    metric = db.daily_metrics.find_one({"business_id": twin.id})
    assert metric["revenue"] == pytest.approx(0.0)
    assert metric["orders"] == 0 and metric["customers"] == 0 and metric["new_customers"] == 0
    # cannot cancel twice
    with pytest.raises(billing.BillingError, match="already cancelled"):
        billing.cancel_bill(db, twin, bill.model_copy(update={"status": "cancelled"}))


def test_pdf_is_generated(db, twin, milk):
    bill = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 2}],
                               customer_name="Priya", discount_pct=5)
    pdf = billing.bill_pdf(twin, bill)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800
