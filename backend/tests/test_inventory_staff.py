"""Stock adjustments, temporary sale prices and staff management."""

from datetime import date, timedelta

import mongomock
import pytest

from app.models import (Business, Product, User, effective_price, insert_model,
                        sale_active, to_dt)
from app.services import billing


@pytest.fixture()
def db():
    return mongomock.MongoClient()["twinbiz_test"]


@pytest.fixture()
def twin(db):
    user = insert_model(db, User(email="s@s.s", full_name="S", password_hash="x"))
    return insert_model(db, Business(owner_id=user.id, name="Stock Mart", employees_count=3))


@pytest.fixture()
def milk(db, twin):
    return insert_model(db, Product(business_id=twin.id, name="Amul Milk 500ml",
                                    price=28, cost=24, stock=50))


def test_effective_price_respects_sale_window(milk):
    assert effective_price(milk) == 28.0
    on_sale = milk.model_copy(update={"sale_price": 24.0, "sale_ends": date.today()})
    assert sale_active(on_sale) and effective_price(on_sale) == 24.0
    expired = milk.model_copy(update={"sale_price": 24.0,
                                      "sale_ends": date.today() - timedelta(days=1)})
    assert not sale_active(expired) and effective_price(expired) == 28.0
    open_ended = milk.model_copy(update={"sale_price": 25.0, "sale_ends": None})
    assert effective_price(open_ended) == 25.0


def test_billing_charges_active_sale_price(db, twin, milk):
    db.products.update_one({"_id": {"$exists": True}},
                           {"$set": {"sale_price": 24.0, "sale_ends": to_dt(date.today())}})
    bill = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 2}])
    assert bill.items[0]["unit_price"] == pytest.approx(24.0)
    assert bill.total == pytest.approx(48.0)


def test_billing_ignores_expired_sale(db, twin, milk):
    db.products.update_one({"_id": {"$exists": True}},
                           {"$set": {"sale_price": 24.0,
                                     "sale_ends": to_dt(date.today() - timedelta(days=3))}})
    bill = billing.create_bill(db, twin, items=[{"product_id": milk.id, "qty": 1}])
    assert bill.items[0]["unit_price"] == pytest.approx(28.0)
