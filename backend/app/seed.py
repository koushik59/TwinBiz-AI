"""Realistic dummy-data generator: 365 days of sales, customers, expenses and
per-product velocity with weekly seasonality, festival spikes, a gentle growth
trend and noise — so charts and ML forecasts work the moment a twin is created."""

import math
import random
from datetime import date, timedelta

from pymongo.database import Database

from .database import next_seq, oid
from .models import Business, DailyMetric, Employee, Product, ProductSale, Supplier

# (name, brand, category, unit_size, price, cost, stock, expiry_days, storage)
SUPERMARKET_CATALOG = [
    ("Amul Milk 500ml", "Amul", "Dairy", "500ml", 28, 24, 140, 4, "refrigerated"),
    ("Amul Butter 100g", "Amul", "Dairy", "100g", 60, 52, 60, 90, "refrigerated"),
    ("Britannia Bread", "Britannia", "Bakery", "400g", 45, 32, 90, 3, "ambient"),
    ("India Gate Rice 5kg", "India Gate", "Rice & Grains", "5kg", 420, 350, 60, 0, "ambient"),
    ("Aashirvaad Atta 5kg", "Aashirvaad", "Rice & Grains", "5kg", 260, 218, 45, 0, "ambient"),
    ("Fortune Oil 1L", "Fortune", "Rice & Grains", "1L", 180, 152, 45, 0, "ambient"),
    ("Eggs (12 pack)", "Local Farm", "Dairy", "12 pcs", 84, 66, 70, 10, "refrigerated"),
    ("Parle-G Biscuits", "Parle", "Snacks", "250g", 30, 20, 200, 90, "ambient"),
    ("Maggi Noodles 4-pack", "Nestle", "Snacks", "280g", 56, 44, 160, 180, "ambient"),
    ("Lays Chips", "Lays", "Snacks", "90g", 20, 14, 180, 60, "ambient"),
    ("Coca-Cola 2L", "Coca-Cola", "Beverages", "2L", 95, 70, 80, 120, "ambient"),
    ("Thums Up 750ml", "Coca-Cola", "Beverages", "750ml", 45, 33, 100, 120, "ambient"),
    ("Tata Tea Gold 500g", "Tata", "Beverages", "500g", 260, 205, 50, 0, "ambient"),
    ("Tata Salt 1kg", "Tata", "Rice & Grains", "1kg", 28, 21, 120, 0, "ambient"),
    ("Surf Excel 1kg", "HUL", "Household", "1kg", 210, 160, 40, 0, "ambient"),
    ("Vim Dishwash Bar", "HUL", "Household", "200g", 20, 13, 150, 0, "ambient"),
    ("Colgate Toothpaste", "Colgate", "Personal Care", "150g", 95, 68, 70, 0, "ambient"),
    ("Dove Shampoo 340ml", "HUL", "Personal Care", "340ml", 240, 175, 35, 0, "ambient"),
    ("Bananas (1 dozen)", "Local", "Fruits", "12 pcs", 60, 42, 50, 4, "ambient"),
    ("Onions 1kg", "Local", "Vegetables", "1kg", 35, 26, 80, 12, "ambient"),
    ("Tomatoes 1kg", "Local", "Vegetables", "1kg", 40, 29, 70, 6, "ambient"),
    ("Amul Ice Cream 1L", "Amul", "Frozen Foods", "1L", 180, 135, 30, 240, "frozen"),
    ("Dairy Milk Chocolate", "Cadbury", "Snacks", "110g", 95, 71, 90, 180, "ambient"),
    ("Regular Lassi 200ml", "Amul", "Dairy", "200ml", 25, 19, 80, 5, "refrigerated"),
]

PRODUCT_CATALOG = {
    "Supermarket": [(n, c, p, co, s, e) for (n, _b, c, _u, p, co, s, e, _st) in SUPERMARKET_CATALOG],
    "Restaurant": [
        ("Veg Thali", "Mains", 180, 95, 999, 1), ("Paneer Butter Masala", "Mains", 260, 130, 999, 1),
        ("Biryani", "Mains", 280, 140, 999, 1), ("Masala Dosa", "Breakfast", 120, 55, 999, 1),
        ("Fresh Lime Soda", "Beverages", 80, 25, 999, 1), ("Gulab Jamun", "Desserts", 90, 35, 999, 1),
        ("Family Combo", "Combos", 850, 420, 999, 1), ("Filter Coffee", "Beverages", 60, 18, 999, 1),
    ],
    "Pharmacy": [
        ("Paracetamol", "Medicine", 30, 21, 300, 365), ("Vitamin C", "Supplements", 180, 120, 120, 365),
        ("Cough Syrup", "Medicine", 110, 78, 80, 365), ("Bandages", "First Aid", 60, 38, 150, 0),
        ("Antiseptic", "First Aid", 95, 64, 90, 365), ("BP Monitor", "Devices", 1800, 1350, 15, 0),
        ("Protein Powder", "Supplements", 1500, 1100, 25, 300), ("Sanitizer", "Hygiene", 75, 48, 200, 365),
    ],
}
PRODUCT_CATALOG["Retail"] = PRODUCT_CATALOG["Supermarket"][:8]
PRODUCT_CATALOG["Bakery"] = [
    ("White Bread", "Bread", 45, 28, 80, 2), ("Chocolate Cake 1kg", "Cakes", 550, 320, 12, 3),
    ("Croissant", "Pastry", 70, 38, 40, 2), ("Cookies 250g", "Cookies", 120, 70, 60, 20),
    ("Puffs", "Savory", 35, 18, 90, 1), ("Birthday Cake", "Cakes", 850, 480, 8, 2),
]
DEFAULT_TYPE = "Supermarket"

EMPLOYEE_NAMES = ["Ravi Kumar", "Priya Sharma", "Amit Patel", "Sneha Reddy", "Vijay Singh",
                  "Anita Desai", "Karthik Rao", "Meena Iyer", "Suresh Nair", "Divya Menon"]
ROLES = ["Manager", "Cashier", "Sales Associate", "Stock Keeper", "Helper"]
SUPPLIER_NAMES = [("Metro Wholesale", "Staples"), ("FreshFarm Traders", "Dairy"),
                  ("City Distributors", "Beverages"), ("Sri Balaji Agencies", "Snacks"),
                  ("National Supply Co", "Household")]

# Indian festival demand spikes (month, day, strength, span-days)
FESTIVALS = [(1, 14, 1.5, 2), (3, 25, 1.6, 2), (8, 15, 1.3, 1), (9, 7, 1.5, 3),
             (10, 2, 1.3, 1), (10, 22, 1.9, 5), (11, 12, 2.1, 5), (12, 25, 1.6, 3)]


def _festival_boost(d: date) -> float:
    boost = 1.0
    for month, day, strength, span in FESTIVALS:
        peak = date(d.year, month, day)
        gap = abs((d - peak).days)
        if gap <= span:
            boost = max(boost, 1 + (strength - 1) * (1 - gap / (span + 1)))
    return boost


def seed_business(db: Database, business: Business) -> None:
    rng = random.Random(int(business.id[-8:], 16) * 7919)
    catalog = PRODUCT_CATALOG.get(business.business_type, PRODUCT_CATALOG[DEFAULT_TYPE])
    sku_prefix = business.id[-4:].upper()

    # --- products ---------------------------------------------------------
    products: list[Product] = []
    scale = business.monthly_revenue / 500000.0  # size twin to declared revenue
    rich = {n: (b, u, st) for (n, b, _c, u, _p, _co, _s, _e, st) in SUPERMARKET_CATALOG}
    for name, cat, price, cost, stock, expiry in catalog:
        brand, unit_size, storage = rich.get(name, ("", "", "ambient"))
        stock_n = max(int(stock * scale * rng.uniform(0.7, 1.3)), 5)
        products.append(Product(
            business_id=business.id, name=name, category=cat, price=price, cost=cost,
            stock=stock_n,
            reorder_level=max(int(stock * 0.25), 5),
            daily_demand=round(stock / 12 * scale * rng.uniform(0.6, 1.4), 1),
            expiry_days=expiry,
            sku=f"SKU-{sku_prefix}-{next_seq(db, f'sku:{business.id}'):04d}",
            brand=brand or None, unit_size=unit_size or None,
            unit_type="pcs", storage_type=storage,
            mrp=round(price * 1.08, 0), tax_rate=5.0,
            min_stock=max(int(stock * 0.1), 3), max_stock=int(stock * 2.5),
            safety_stock=max(int(stock * 0.15), 3), reorder_qty=max(int(stock * 0.8), 10),
            supplier_cost=round(cost * 0.97, 2), lead_time_days=rng.randint(1, 5),
            moq=10, is_demo=1,
        ))
    inserted = db.products.insert_many([p.to_doc() for p in products])
    for p, _id in zip(products, inserted.inserted_ids):
        p.id = str(_id)
    db.businesses.update_one({"_id": oid(business.id)}, {"$set": {"data_source": "demo"}})
    business.data_source = "demo"

    # --- employees & suppliers ---------------------------------------------
    employees = [Employee(
        business_id=business.id, name=EMPLOYEE_NAMES[i % len(EMPLOYEE_NAMES)],
        role=ROLES[0] if i == 0 else ROLES[1 + i % (len(ROLES) - 1)],
        salary=32000 if i == 0 else rng.randint(14000, 22000),
        department="Management" if i == 0 else "Operations",
        performance=round(rng.uniform(0.6, 0.97), 2),
    ) for i in range(business.employees_count)]
    if employees:
        db.employees.insert_many([e.to_doc() for e in employees])
    db.suppliers.insert_many([Supplier(
        business_id=business.id, name=name, category=cat,
        reliability=round(rng.uniform(0.75, 0.98), 2),
        lead_time_days=rng.randint(1, 7),
        cost_index=round(rng.uniform(0.92, 1.1), 2),
    ).to_doc() for name, cat in SUPPLIER_NAMES[:4]])

    # --- 365 days of history ---------------------------------------------------
    today = date.today()
    base_daily_rev = business.monthly_revenue / 30.0
    base_daily_customers = business.customer_count / 30.0 if business.customer_count else 40
    weekday_mult = [0.86, 0.90, 0.94, 0.98, 1.08, 1.28, 1.22]  # Mon..Sun

    metrics, sales_rows = [], []
    for i in range(365):
        d = today - timedelta(days=364 - i)
        growth = 1 + 0.10 * (i / 365)                      # ~10% YoY growth
        season = 1 + 0.06 * math.sin(2 * math.pi * (i / 365) * 2)
        mult = weekday_mult[d.weekday()] * _festival_boost(d) * growth * season
        noise = rng.gauss(1.0, 0.07)
        revenue = max(base_daily_rev * mult * noise, base_daily_rev * 0.3)
        expenses = business.monthly_expenses / 30.0 * (0.55 + 0.45 * mult) * rng.gauss(1.0, 0.04)
        customers = max(int(base_daily_customers * mult * rng.gauss(1.0, 0.09)), 5)
        orders = max(int(customers * rng.uniform(0.55, 0.8)), 3)
        metrics.append(DailyMetric(
            business_id=business.id, day=d,
            revenue=round(revenue, 0), expenses=round(expenses, 0),
            customers=customers, orders=orders,
            new_customers=max(int(customers * rng.uniform(0.05, 0.14)), 1),
            inventory_value=round(sum(p.stock * p.cost for p in products) * rng.uniform(0.85, 1.15), 0),
        ).to_doc())
        # product-level sales for the last 120 days (enough for velocity analytics);
        # units track each product's configured daily demand so velocities are consistent
        if i >= 245:
            for p in products:
                units = max(int(p.daily_demand * mult * rng.gauss(1.0, 0.18)), 0)
                if units:
                    sales_rows.append(ProductSale(
                        business_id=business.id, product_id=p.id, day=d,
                        units=units, revenue=round(units * p.price, 0),
                    ).to_doc())

    db.daily_metrics.insert_many(metrics)
    if sales_rows:
        db.product_sales.insert_many(sales_rows)
