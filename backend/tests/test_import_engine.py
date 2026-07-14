"""Import-engine commit tests: upsert-by-key semantics on a mongomock twin."""

from datetime import date, datetime

import mongomock
import pytest

from app.models import Business, Product, User, insert_model
from app.services.import_engine import commit_rows


@pytest.fixture()
def db():
    return mongomock.MongoClient()["twinbiz_test"]


@pytest.fixture()
def twin(db):
    user = insert_model(db, User(email="i@i.i", full_name="I", password_hash="x"))
    biz = insert_model(db, Business(owner_id=user.id, name="Import Mart"))
    insert_model(db, Product(business_id=biz.id, name="Amul Milk 500ml", sku="SKU-1",
                             price=28, cost=24, stock=100, daily_demand=20, is_demo=1))
    return biz


def test_products_upsert_by_sku_and_name(db, twin):
    rows = [
        {"name": "Amul Milk 500ml", "sku": "SKU-1", "price": 30.0},  # update existing
        {"name": "New Butter", "price": 60.0},                        # insert new
    ]
    counts = commit_rows(db, twin, "products", rows)
    assert counts == {"created": 1, "updated": 1, "skipped": 0}
    milk = db.products.find_one({"sku": "SKU-1"})
    assert milk["price"] == 30.0
    assert milk["is_demo"] == 0  # imported data marks the row as real
    butter = db.products.find_one({"name": "New Butter"})
    assert butter["cost"] == pytest.approx(45.0)  # defaulted to 75% of price
    assert db.businesses.find_one()["data_source"] == "mixed"


def test_sales_upsert_on_business_product_day(db, twin):
    d = date(2026, 7, 1)
    rows = [{"product": "amul milk 500ml", "day": d, "units": 10}]
    first = commit_rows(db, twin, "sales", rows)
    assert first["created"] == 1
    again = commit_rows(db, twin, "sales", [{"product": "SKU-1", "day": d, "units": 14}])
    assert again == {"created": 0, "updated": 1, "skipped": 0}
    docs = list(db.product_sales.find({}))
    assert len(docs) == 1
    assert docs[0]["units"] == 14
    assert docs[0]["day"] == datetime(2026, 7, 1)  # stored as BSON datetime
    # unknown product names are skipped, never crash
    skipped = commit_rows(db, twin, "sales", [{"product": "ghost", "day": d, "units": 1}])
    assert skipped["skipped"] == 1


def test_daily_metrics_upsert_on_day(db, twin):
    d = date(2026, 7, 2)
    commit_rows(db, twin, "daily_metrics", [{"day": d, "revenue": 1000.0, "customers": 50}])
    counts = commit_rows(db, twin, "daily_metrics", [{"day": d, "revenue": 1200.0}])
    assert counts == {"created": 0, "updated": 1, "skipped": 0}
    docs = list(db.daily_metrics.find({}))
    assert len(docs) == 1
    assert docs[0]["revenue"] == 1200.0
    assert docs[0]["customers"] == 50  # untouched fields survive the second import


def test_expenses_fold_into_daily_metric(db, twin):
    d = date(2026, 7, 3)
    commit_rows(db, twin, "expenses", [{"day": d, "amount": 300.0}])
    commit_rows(db, twin, "expenses", [{"day": d, "amount": 200.0}])
    doc = db.daily_metrics.find_one({"business_id": twin.id})
    assert doc["expenses"] == 500.0  # $inc accumulates like the old += fold
    assert doc["revenue"] == 0.0     # inserted with sane defaults
