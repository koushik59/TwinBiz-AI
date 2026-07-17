import certifi
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .config import settings

# One module-level client: thread-safe and pooled, shared across FastAPI's
# threadpool workers. tlsCAFile fixes Atlas TLS verification on hosts with
# stale CA bundles (e.g. Render's base image).
_needs_tls = settings.mongodb_uri.startswith("mongodb+srv://") or "mongodb.net" in settings.mongodb_uri
client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=8000,
    maxPoolSize=50,
    **({"tlsCAFile": certifi.where()} if _needs_tls else {}),
)
_db: Database = client[settings.mongodb_db]

# Sentinel that can never match a real document (used for malformed ids so
# lookups return None -> clean 404 instead of a bson 500).
_NO_MATCH = ObjectId("0" * 24)


def get_db() -> Database:
    return _db


def oid(id_str: str) -> ObjectId:
    """Parse a client-supplied id string; malformed input matches nothing."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return _NO_MATCH


def next_seq(db: Database, key: str) -> int:
    """Atomic per-key counter (SKU numbering etc.)."""
    doc = db.counters.find_one_and_update(
        {"_id": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
    )
    return int(doc["seq"])


def ensure_indexes(db: Database) -> None:
    db.users.create_index("email", unique=True)
    db.businesses.create_index("owner_id")
    db.products.create_index([("business_id", ASCENDING), ("category", ASCENDING)])
    db.products.create_index([("business_id", ASCENDING), ("sku", ASCENDING)])
    db.employees.create_index("business_id")
    db.suppliers.create_index("business_id")
    db.daily_metrics.create_index(
        [("business_id", ASCENDING), ("day", ASCENDING)], unique=True
    )
    db.product_sales.create_index(
        [("business_id", ASCENDING), ("product_id", ASCENDING), ("day", ASCENDING)]
    )
    db.product_sales.create_index([("business_id", ASCENDING), ("day", ASCENDING)])
    db.scenarios.create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    db.product_experiments.create_index(
        [("business_id", ASCENDING), ("created_at", DESCENDING)]
    )
    db.product_experiment_scenarios.create_index(
        [("experiment_id", ASCENDING), ("created_at", DESCENDING)]
    )
    db.chat_messages.create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    db.decisions.create_index([("business_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.stock_snapshots.create_index([("business_id", ASCENDING), ("day", ASCENDING)], unique=True)
    db.bills.create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    db.bills.create_index([("business_id", ASCENDING), ("customer_phone", ASCENDING)])
    db.stock_adjustments.create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
