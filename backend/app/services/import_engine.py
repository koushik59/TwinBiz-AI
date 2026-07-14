"""Data Center import engine (§7): parse CSV/XLSX, auto-map columns, validate
every row, and commit clean rows into the twin. Invalid data is never silently
ignored — each import returns a full validation report."""

import io
import re
from datetime import date, datetime

import pandas as pd
from pymongo.database import Database

from ..database import oid
from ..models import (Business, DailyMetric, Employee, Product, ProductSale,
                      Supplier, find_models, to_dt)

MAX_ROWS = 5000

# target fields per data type: name -> (required, kind)
SCHEMAS: dict[str, dict[str, tuple[bool, str]]] = {
    "products": {
        "name": (True, "str"), "sku": (False, "str"), "barcode": (False, "str"),
        "brand": (False, "str"), "category": (False, "str"), "subcategory": (False, "str"),
        "unit_type": (False, "str"), "unit_size": (False, "str"),
        "price": (True, "money"), "cost": (False, "money"), "mrp": (False, "money"),
        "tax_rate": (False, "float"), "stock": (False, "int"),
        "reorder_level": (False, "int"), "daily_demand": (False, "float"),
        "expiry_days": (False, "int"), "storage_type": (False, "str"),
        "shelf_location": (False, "str"),
    },
    "sales": {
        "product": (True, "str"), "day": (True, "date"),
        "units": (True, "int"), "revenue": (False, "money"),
    },
    "daily_metrics": {
        "day": (True, "date"), "revenue": (True, "money"), "expenses": (False, "money"),
        "customers": (False, "int"), "orders": (False, "int"), "new_customers": (False, "int"),
    },
    "expenses": {
        "day": (True, "date"), "amount": (True, "money"), "category": (False, "str"),
    },
    "suppliers": {
        "name": (True, "str"), "category": (False, "str"),
        "lead_time_days": (False, "int"), "reliability": (False, "float"),
    },
    "employees": {
        "name": (True, "str"), "role": (False, "str"), "salary": (False, "money"),
        "department": (False, "str"),
    },
}

# header synonyms → target field (per data type; lowercase, stripped of symbols)
SYNONYMS: dict[str, dict[str, str]] = {
    "products": {
        "name": "name", "productname": "name", "itemname": "name", "product": "name",
        "item": "name", "title": "name", "description": "name",
        "sku": "sku", "skucode": "sku", "itemcode": "sku", "productcode": "sku", "code": "sku",
        "barcode": "barcode", "ean": "barcode", "upc": "barcode",
        "brand": "brand", "company": "brand", "manufacturer": "brand",
        "category": "category", "productcategory": "category", "group": "category",
        "subcategory": "subcategory",
        "unit": "unit_type", "unittype": "unit_type", "uom": "unit_type",
        "unitsize": "unit_size", "size": "unit_size", "weight": "unit_size", "pack": "unit_size",
        "price": "price", "saleprice": "price", "sellingprice": "price", "rate": "price",
        "sellprice": "price", "retailprice": "price",
        "cost": "cost", "costprice": "cost", "purchaseprice": "cost", "buyprice": "cost",
        "purchaserate": "cost", "landedcost": "cost",
        "mrp": "mrp", "maxretailprice": "mrp", "listprice": "mrp",
        "tax": "tax_rate", "taxrate": "tax_rate", "gst": "tax_rate", "gstrate": "tax_rate", "vat": "tax_rate",
        "stock": "stock", "qty": "stock", "quantity": "stock", "quantityonhand": "stock",
        "currentstock": "stock", "onhand": "stock", "openingstock": "stock", "closingstock": "stock",
        "reorderlevel": "reorder_level", "reorderpoint": "reorder_level", "minstock": "reorder_level",
        "dailydemand": "daily_demand", "avgdailysales": "daily_demand", "dailysales": "daily_demand",
        "velocity": "daily_demand",
        "expirydays": "expiry_days", "shelflife": "expiry_days", "shelflifedays": "expiry_days",
        "storage": "storage_type", "storagetype": "storage_type",
        "shelf": "shelf_location", "shelflocation": "shelf_location", "location": "shelf_location",
        "aisle": "shelf_location",
    },
    "sales": {
        "product": "product", "productname": "product", "item": "product", "itemname": "product",
        "name": "product", "sku": "product", "skucode": "product",
        "day": "day", "date": "day", "saledate": "day", "solddate": "day", "soldat": "day",
        "billdate": "day", "invoicedate": "day", "transactiondate": "day",
        "units": "units", "qty": "units", "quantity": "units", "unitssold": "units",
        "qtysold": "units", "count": "units",
        "revenue": "revenue", "amount": "revenue", "total": "revenue", "totalamount": "revenue",
        "saleamount": "revenue", "value": "revenue", "salevalue": "revenue",
    },
    "daily_metrics": {
        "day": "day", "date": "day",
        "revenue": "revenue", "sales": "revenue", "totalsales": "revenue", "turnover": "revenue",
        "amount": "revenue",
        "expenses": "expenses", "expense": "expenses", "cost": "expenses", "costs": "expenses",
        "spend": "expenses",
        "customers": "customers", "footfall": "customers", "visitors": "customers",
        "customercount": "customers",
        "orders": "orders", "bills": "orders", "transactions": "orders", "invoices": "orders",
        "newcustomers": "new_customers",
    },
    "expenses": {
        "day": "day", "date": "day", "expensedate": "day", "paiddate": "day",
        "amount": "amount", "expense": "amount", "value": "amount", "total": "amount", "cost": "amount",
        "category": "category", "type": "category", "expensetype": "category", "head": "category",
        "description": "category",
    },
    "suppliers": {
        "name": "name", "suppliername": "name", "supplier": "name", "vendor": "name",
        "vendorname": "name", "company": "name",
        "category": "category", "type": "category", "supplies": "category",
        "leadtime": "lead_time_days", "leadtimedays": "lead_time_days", "deliverydays": "lead_time_days",
        "reliability": "reliability", "reliabilityscore": "reliability", "rating": "reliability",
    },
    "employees": {
        "name": "name", "employeename": "name", "employee": "name", "staffname": "name",
        "fullname": "name",
        "role": "role", "designation": "role", "position": "role", "jobtitle": "role",
        "salary": "salary", "pay": "salary", "wage": "salary", "monthlysalary": "salary", "ctc": "salary",
        "department": "department", "dept": "department", "team": "department",
    },
}


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h).lower())


def parse_file(filename: str, content: bytes) -> pd.DataFrame:
    """Parse CSV or XLSX bytes into a DataFrame of strings."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), dtype=str)
    else:
        try:
            df = pd.read_csv(io.BytesIO(content), dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), dtype=str, encoding="latin-1")
    if len(df) > MAX_ROWS:
        raise ValueError(f"File has {len(df)} rows; maximum supported is {MAX_ROWS}.")
    df.columns = [str(c).strip() for c in df.columns]
    return df.astype(object).where(pd.notna(df), None)


def suggest_mapping(data_type: str, columns: list[str]) -> dict[str, str | None]:
    """column header -> suggested target field (or None)."""
    syn = SYNONYMS[data_type]
    used: set[str] = set()
    mapping: dict[str, str | None] = {}
    for col in columns:
        target = syn.get(_norm_header(col))
        if target and target not in used:
            mapping[col] = target
            used.add(target)
        else:
            mapping[col] = None
    return mapping


def _parse_value(raw, kind: str):
    """Returns (value, error). raw is a string or None."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, None
    s = str(raw).strip()
    if kind == "str":
        return s, None
    if kind in ("money", "float"):
        cleaned = re.sub(r"[₹$,\s]", "", s)
        try:
            v = float(cleaned)
        except ValueError:
            return None, f"'{s}' is not a number"
        if kind == "money" and v < 0:
            return None, f"negative amount {v}"
        return v, None
    if kind == "int":
        cleaned = re.sub(r"[,\s]", "", s)
        try:
            v = int(float(cleaned))
        except ValueError:
            return None, f"'{s}' is not a whole number"
        if v < 0:
            return None, f"negative count {v}"
        return v, None
    if kind == "date":
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d %b %Y", "%d-%b-%Y"):
            try:
                return datetime.strptime(s.split(" ")[0], fmt).date(), None
            except ValueError:
                continue
        try:  # pandas fallback handles ISO datetimes, excel serials already converted
            return pd.to_datetime(s, dayfirst=True).date(), None
        except Exception:
            return None, f"'{s}' is not a recognizable date"
    return s, None


def validate_rows(data_type: str, df: pd.DataFrame, mapping: dict[str, str]) -> dict:
    """Apply mapping, parse and validate every row.

    Returns {rows: [parsed dicts], report: {...}} where report lists every problem.
    """
    schema = SCHEMAS[data_type]
    active = {col: field for col, field in mapping.items() if field and col in df.columns}
    mapped_fields = set(active.values())
    missing_required = [f for f, (req, _) in schema.items() if req and f not in mapped_fields]
    if missing_required:
        return {"rows": [], "report": {
            "total": len(df), "valid": 0, "invalid": len(df), "duplicates": 0,
            "errors": [{"row": None, "problem": f"Required column not mapped: {f}"} for f in missing_required],
            "warnings": [],
        }}

    rows, errors, warnings = [], [], []
    seen_keys: set = set()
    duplicates = 0
    for i, rec in enumerate(df.to_dict(orient="records")):
        row_num = i + 2  # 1-based + header row
        parsed: dict = {}
        row_errors = []
        failed_fields: set[str] = set()
        for col, field in active.items():
            _req, kind = schema[field]
            value, err = _parse_value(rec.get(col), kind)
            if err:
                row_errors.append(f"{col}: {err}")
                failed_fields.add(field)
            elif value is not None:
                parsed[field] = value
        for f, (req, _) in schema.items():
            if req and f not in parsed and f not in failed_fields:
                row_errors.append(f"missing required value: {f}")
        if data_type in ("sales", "daily_metrics", "expenses") and isinstance(parsed.get("day"), date):
            if parsed["day"] > date.today():
                row_errors.append(f"day {parsed['day']} is in the future")
        if row_errors:
            errors.append({"row": row_num, "problem": "; ".join(row_errors)})
            continue
        # duplicate detection
        key = None
        if data_type == "products":
            key = (parsed.get("sku") or parsed["name"]).lower()
        elif data_type == "sales":
            key = (parsed["product"].lower(), parsed["day"])
        elif data_type in ("daily_metrics",):
            key = parsed["day"]
        elif data_type in ("suppliers", "employees"):
            key = parsed["name"].lower()
        if key is not None:
            if key in seen_keys:
                duplicates += 1
                warnings.append({"row": row_num, "problem": "duplicate of an earlier row — skipped"})
                continue
            seen_keys.add(key)
        rows.append(parsed)

    return {"rows": rows, "report": {
        "total": len(df), "valid": len(rows), "invalid": len(errors),
        "duplicates": duplicates, "errors": errors[:100], "warnings": warnings[:100],
    }}


def commit_rows(db: Database, business: Business, data_type: str, rows: list[dict]) -> dict:
    """Insert validated rows into the twin. Returns per-action counts."""
    created = updated = skipped = 0

    if data_type == "products":
        all_products = find_models(db, Product, {"business_id": business.id})
        existing = {(p.sku or p.name).lower(): p for p in all_products}
        by_name = {p.name.lower(): p for p in all_products}
        for r in rows:
            key = (r.get("sku") or r["name"]).lower()
            match = existing.get(key) or by_name.get(r["name"].lower())
            if match:
                db.products.update_one({"_id": oid(match.id)},
                                       {"$set": {**r, "is_demo": 0}})
                updated += 1
            else:
                p = Product(business_id=business.id, is_demo=0,
                            cost=r.get("cost", round(r["price"] * 0.75, 2)), **{
                                k: v for k, v in r.items() if k != "cost"})
                db.products.insert_one(p.to_doc())
                created += 1

    elif data_type == "sales":
        products = find_models(db, Product, {"business_id": business.id})
        lookup: dict[str, Product] = {}
        for p in products:
            lookup[p.name.lower()] = p
            if p.sku:
                lookup[p.sku.lower()] = p
        for r in rows:
            p = lookup.get(r["product"].lower())
            if not p:
                skipped += 1
                continue
            revenue = r.get("revenue", r["units"] * p.price)
            result = db.product_sales.update_one(
                {"business_id": business.id, "product_id": p.id, "day": to_dt(r["day"])},
                {"$set": {"units": r["units"], "revenue": revenue}},
                upsert=True,
            )
            if result.upserted_id is not None:
                created += 1
            else:
                updated += 1

    elif data_type == "daily_metrics":
        for r in rows:
            fields = {f: v for f, v in r.items() if f != "day"}
            result = db.daily_metrics.update_one(
                {"business_id": business.id, "day": to_dt(r["day"])},
                {"$set": fields,
                 "$setOnInsert": {k: v for k, v in DailyMetric(
                     business_id=business.id, day=r["day"]).to_doc().items()
                     if k not in fields and k not in ("business_id", "day")}},
                upsert=True,
            )
            if result.upserted_id is not None:
                created += 1
            else:
                updated += 1

    elif data_type == "expenses":
        # expenses fold into the daily metric row for that day
        for r in rows:
            result = db.daily_metrics.update_one(
                {"business_id": business.id, "day": to_dt(r["day"])},
                {"$inc": {"expenses": r["amount"]},
                 "$setOnInsert": {"revenue": 0.0, "customers": 0, "orders": 0,
                                  "new_customers": 0, "inventory_value": 0.0}},
                upsert=True,
            )
            if result.upserted_id is not None:
                created += 1
            else:
                updated += 1

    elif data_type == "suppliers":
        existing = {s.name.lower(): s for s in
                    find_models(db, Supplier, {"business_id": business.id})}
        for r in rows:
            match = existing.get(r["name"].lower())
            if match:
                db.suppliers.update_one({"_id": oid(match.id)}, {"$set": r})
                updated += 1
            else:
                db.suppliers.insert_one(Supplier(business_id=business.id, **r).to_doc())
                created += 1

    elif data_type == "employees":
        existing = {e.name.lower(): e for e in
                    find_models(db, Employee, {"business_id": business.id})}
        for r in rows:
            match = existing.get(r["name"].lower())
            if match:
                db.employees.update_one({"_id": oid(match.id)}, {"$set": r})
                updated += 1
            else:
                db.employees.insert_one(Employee(business_id=business.id, **r).to_doc())
                created += 1

    if business.data_source == "demo":
        db.businesses.update_one({"_id": oid(business.id)},
                                 {"$set": {"data_source": "mixed"}})
        business.data_source = "mixed"
    return {"created": created, "updated": updated, "skipped": skipped}
