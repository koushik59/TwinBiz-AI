"""Realistic dummy-data generator: 365 days of sales, customers, expenses and
per-product velocity with weekly seasonality, festival spikes, a gentle growth
trend and noise — so charts and ML forecasts work the moment a twin is created."""

import math
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .models import Business, DailyMetric, Employee, Product, ProductSale, Supplier

PRODUCT_CATALOG = {
    "Supermarket": [
        ("Milk 1L", "Dairy", 62, 54, 120, 4), ("Bread", "Bakery", 45, 32, 90, 3),
        ("Rice 5kg", "Staples", 420, 350, 60, 0), ("Cooking Oil 1L", "Staples", 180, 152, 45, 0),
        ("Eggs (12)", "Dairy", 84, 66, 70, 10), ("Biscuits", "Snacks", 30, 20, 200, 90),
        ("Detergent 1kg", "Household", 210, 160, 40, 0), ("Shampoo", "Personal Care", 240, 175, 35, 0),
        ("Cold Drink 2L", "Beverages", 95, 70, 80, 120), ("Atta 10kg", "Staples", 480, 410, 30, 0),
        ("Tea 500g", "Beverages", 260, 205, 50, 0), ("Chocolates", "Snacks", 50, 34, 150, 180),
    ],
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


def seed_business(db: Session, business: Business) -> None:
    rng = random.Random(business.id * 7919)
    catalog = PRODUCT_CATALOG.get(business.business_type, PRODUCT_CATALOG[DEFAULT_TYPE])

    # --- products ---------------------------------------------------------
    products: list[Product] = []
    scale = business.monthly_revenue / 500000.0  # size twin to declared revenue
    for name, cat, price, cost, stock, expiry in catalog:
        p = Product(
            business_id=business.id, name=name, category=cat, price=price, cost=cost,
            stock=max(int(stock * scale * rng.uniform(0.7, 1.3)), 5),
            reorder_level=max(int(stock * 0.25), 5),
            daily_demand=round(stock / 12 * scale * rng.uniform(0.6, 1.4), 1),
            expiry_days=expiry,
        )
        products.append(p)
        db.add(p)

    # --- employees & suppliers ---------------------------------------------
    for i in range(business.employees_count):
        db.add(Employee(
            business_id=business.id, name=EMPLOYEE_NAMES[i % len(EMPLOYEE_NAMES)],
            role=ROLES[0] if i == 0 else ROLES[1 + i % (len(ROLES) - 1)],
            salary=32000 if i == 0 else rng.randint(14000, 22000),
            department="Management" if i == 0 else "Operations",
            performance=round(rng.uniform(0.6, 0.97), 2),
        ))
    for name, cat in SUPPLIER_NAMES[:4]:
        db.add(Supplier(
            business_id=business.id, name=name, category=cat,
            reliability=round(rng.uniform(0.75, 0.98), 2),
            lead_time_days=rng.randint(1, 7),
            cost_index=round(rng.uniform(0.92, 1.1), 2),
        ))
    db.flush()

    # --- 365 days of history ---------------------------------------------------
    today = date.today()
    base_daily_rev = business.monthly_revenue / 30.0
    base_daily_customers = business.customer_count / 30.0 if business.customer_count else 40
    weekday_mult = [0.86, 0.90, 0.94, 0.98, 1.08, 1.28, 1.22]  # Mon..Sun
    weights = [max(p.daily_demand * p.price, 1) for p in products]
    total_w = sum(weights)

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
        ))
        # product-level sales for the last 120 days (enough for velocity analytics)
        if i >= 245:
            for p, w in zip(products, weights):
                share = w / total_w
                units = max(int(orders * share * rng.uniform(0.5, 1.6) * 3), 0)
                if units:
                    sales_rows.append(ProductSale(
                        business_id=business.id, product_id=p.id, day=d,
                        units=units, revenue=round(units * p.price, 0),
                    ))

    db.add_all(metrics)
    db.add_all(sales_rows)
    db.commit()
