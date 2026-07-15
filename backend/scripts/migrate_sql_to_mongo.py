"""One-time data migration: old SQLAlchemy database (SQLite/Postgres) -> MongoDB.

Standalone by design: it reflects the SQL schema instead of importing app.models
(which is now Mongo-based). SQLAlchemy is no longer in requirements.txt, so
install it ad-hoc before running:

    .venv/Scripts/python -m pip install sqlalchemy          # + psycopg2-binary for Postgres sources

Usage (run from backend/):

    .venv/Scripts/python scripts/migrate_sql_to_mongo.py \
        --sql-url sqlite:///./twinbiz.db \
        --mongo-uri "mongodb+srv://user:pass@cluster.mongodb.net" \
        --db twinbiz [--drop] [--dry-run]

Defaults: --sql-url from $DATABASE_URL or sqlite:///./twinbiz.db,
--mongo-uri from $MONGODB_URI, --db from $MONGODB_DB or "twinbiz".

Int primary keys become ObjectIds; foreign keys are remapped to the new
24-hex string ids (matching the app's storage convention). date columns become
BSON datetimes at midnight. Rows pointing at missing parents are skipped and
reported. daily_metrics is deduped on (business_id, day), keeping the last row,
so the app's unique index can be created afterwards.

Exit code is non-zero if any table's migrated count mismatches (excluding
intentionally skipped rows).
"""

import argparse
import os
import sys
from datetime import date, datetime, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bson import ObjectId
from pymongo import MongoClient

try:
    from sqlalchemy import MetaData, create_engine, select
except ImportError:
    sys.exit("sqlalchemy is required for this one-time migration: "
             "pip install sqlalchemy (and psycopg2-binary for Postgres sources)")

# (table, [fk_column -> parent table]) in dependency order
TABLES: list[tuple[str, dict[str, str]]] = [
    ("users", {}),
    ("businesses", {"owner_id": "users"}),
    ("suppliers", {"business_id": "businesses"}),
    ("products", {"business_id": "businesses", "supplier_id": "suppliers"}),
    ("employees", {"business_id": "businesses"}),
    ("daily_metrics", {"business_id": "businesses"}),
    ("product_sales", {"business_id": "businesses", "product_id": "products"}),
    ("scenarios", {"business_id": "businesses"}),
    ("product_experiments", {"business_id": "businesses"}),
    ("product_experiment_scenarios", {"experiment_id": "product_experiments"}),
    ("chat_messages", {"business_id": "businesses"}),
]

# FK columns that may legitimately be NULL (skip remap instead of dropping the row)
NULLABLE_FKS = {("products", "supplier_id")}

BATCH = 1000


def to_bson(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sql-url", default=os.environ.get("DATABASE_URL", "sqlite:///./twinbiz.db"))
    ap.add_argument("--mongo-uri", default=os.environ.get("MONGODB_URI", ""))
    ap.add_argument("--db", default=os.environ.get("MONGODB_DB", "twinbiz"))
    ap.add_argument("--drop", action="store_true",
                    help="drop target collections before migrating")
    ap.add_argument("--dry-run", action="store_true",
                    help="read + convert + report, but write nothing to Mongo")
    args = ap.parse_args()
    if not args.mongo_uri and not args.dry_run:
        sys.exit("--mongo-uri (or $MONGODB_URI) is required")

    engine = create_engine(args.sql_url)
    meta = MetaData()
    meta.reflect(engine)

    target = None
    if not args.dry_run:
        mongo = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=10000)
        target = mongo[args.db]
        mongo.admin.command("ping")

    id_maps: dict[str, dict[int, str]] = {}
    results: list[tuple[str, int, int, int]] = []  # table, sql_count, migrated, skipped
    failed = False

    for table_name, fks in TABLES:
        if table_name not in meta.tables:
            print(f"  {table_name:32s} (table missing in source — skipped)")
            id_maps[table_name] = {}
            continue
        table = meta.tables[table_name]
        with engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(select(table))]
        sql_count = len(rows)

        if args.drop and not args.dry_run:
            target[table_name].drop()

        # dedupe daily_metrics on (business_id, day) keeping the LAST row,
        # so the app's unique index can be built afterwards
        if table_name == "daily_metrics":
            deduped: dict[tuple, dict] = {}
            for r in rows:
                deduped[(r["business_id"], r["day"])] = r
            rows = list(deduped.values())

        id_map: dict[int, str] = {r["id"]: str(ObjectId()) for r in rows}
        id_maps[table_name] = id_map

        docs, skipped = [], 0
        for r in rows:
            doc = {}
            orphan = False
            for col, value in r.items():
                if col == "id":
                    continue
                if col in fks:
                    if value is None and (table_name, col) in NULLABLE_FKS:
                        doc[col] = None
                        continue
                    mapped = id_maps[fks[col]].get(value)
                    if mapped is None:
                        orphan = True
                        break
                    doc[col] = mapped
                else:
                    doc[col] = to_bson(value)
            if orphan:
                skipped += 1
                continue
            doc["_id"] = ObjectId(id_map[r["id"]])
            docs.append(doc)

        if not args.dry_run:
            for i in range(0, len(docs), BATCH):
                target[table_name].insert_many(docs[i:i + BATCH], ordered=False)

        migrated = len(docs)
        results.append((table_name, sql_count, migrated, skipped))
        dedup_note = f" (deduped from {sql_count})" if table_name == "daily_metrics" and len(rows) != sql_count else ""
        print(f"  {table_name:32s} sql={sql_count:6d}  mongo={migrated:6d}  skipped={skipped}{dedup_note}")
        if migrated + skipped != len(rows):
            failed = True

    if not args.dry_run:
        # SKU counters: continue numbering after each business's existing products
        for biz_sql_id, biz_mongo_id in id_maps.get("businesses", {}).items():
            n = target.products.count_documents({"business_id": biz_mongo_id})
            target.counters.update_one({"_id": f"sku:{biz_mongo_id}"},
                                       {"$set": {"seq": n}}, upsert=True)
        from app.database import ensure_indexes
        ensure_indexes(target)
        print("Indexes created; SKU counters seeded.")

    print("\nVerification:")
    for table_name, sql_count, migrated, skipped in results:
        mongo_count = target[table_name].count_documents({}) if not args.dry_run else migrated
        ok = mongo_count >= migrated
        if not ok:
            failed = True
        print(f"  {table_name:32s} mongo has {mongo_count} (migrated {migrated}, "
              f"skipped {skipped} orphans) {'OK' if ok else 'MISMATCH'}")

    if failed:
        print("\nMIGRATION INCOMPLETE — see mismatches above.")
        return 1
    print("\nMigration complete." + (" (dry run — nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
