"""MongoDB document models.

Each model wraps one document from its COLLECTION. The only ObjectId boundary
is `_id` <-> `id` (str); reference fields (owner_id, business_id, product_id,
supplier_id, experiment_id) are stored as plain 24-hex strings so filters can
use `business.id` directly. Fields in DATE_FIELDS are `date` in Python but
stored as BSON datetime at midnight (BSON has no date-only type).
"""

from datetime import date, datetime, timezone
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field
from pymongo.database import Database


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_dt(d: date) -> datetime:
    """date -> BSON-encodable datetime at midnight (also used in query filters)."""
    if isinstance(d, datetime):
        return d
    return datetime(d.year, d.month, d.day)


class MongoModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    COLLECTION: ClassVar[str] = ""
    DATE_FIELDS: ClassVar[tuple[str, ...]] = ()

    id: str = ""

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "MongoModel":
        data = dict(doc)
        data["id"] = str(data.pop("_id"))
        for f in cls.DATE_FIELDS:
            v = data.get(f)
            if isinstance(v, datetime):
                data[f] = v.date()
        return cls(**data)

    def to_doc(self) -> dict[str, Any]:
        doc = self.model_dump(exclude={"id"})
        for f in self.DATE_FIELDS:
            v = doc.get(f)
            if isinstance(v, date) and not isinstance(v, datetime):
                doc[f] = to_dt(v)
        return doc


def find_models(db: Database, model_cls, filt: dict, sort=None, skip: int = 0, limit: int = 0) -> list:
    cur = db[model_cls.COLLECTION].find(filt)
    if sort:
        cur = cur.sort(sort)
    if skip:
        cur = cur.skip(skip)
    if limit:
        cur = cur.limit(limit)
    return [model_cls.from_doc(d) for d in cur]


def get_owned(db: Database, model_cls, id_str: str, business_id: str, owner_field: str = "business_id"):
    """Fetch a document by id, scoped to its owning business/experiment. None -> caller 404s."""
    from .database import oid

    doc = db[model_cls.COLLECTION].find_one({"_id": oid(id_str), owner_field: business_id})
    return model_cls.from_doc(doc) if doc else None


def insert_model(db: Database, m: MongoModel) -> MongoModel:
    res = db[m.COLLECTION].insert_one(m.to_doc())
    m.id = str(res.inserted_id)
    return m


class User(MongoModel):
    COLLECTION: ClassVar[str] = "users"

    email: str
    full_name: str
    password_hash: str
    role: str = "owner"
    created_at: datetime = Field(default_factory=utcnow)


class Business(MongoModel):
    COLLECTION: ClassVar[str] = "businesses"

    owner_id: str
    name: str
    business_type: str = "Supermarket"
    location: str = ""
    employees_count: int = 5
    monthly_revenue: float = 500000.0
    monthly_expenses: float = 380000.0
    customer_count: int = 1200
    working_hours: str = "9:00-21:00"
    currency: str = "₹"
    # "demo" = seeded synthetic history, "real" = user data, "mixed" = both
    data_source: str = "demo"
    created_at: datetime = Field(default_factory=utcnow)


class Product(MongoModel):
    COLLECTION: ClassVar[str] = "products"
    DATE_FIELDS: ClassVar[tuple[str, ...]] = ("sale_ends",)

    business_id: str
    name: str
    category: str = "General"
    price: float = 100.0   # regular selling price
    cost: float = 70.0     # cost price
    # temporary promotional price; active while set and (sale_ends is empty or not past)
    sale_price: float | None = None
    sale_ends: date | None = None
    stock: int = 100
    reorder_level: int = 30  # reorder point
    daily_demand: float = 10.0
    expiry_days: int = 0  # shelf life; 0 = non-perishable

    # -- extended catalog fields ---------------------------------------------
    sku: str | None = None
    barcode: str | None = None
    brand: str | None = None
    subcategory: str | None = None
    description: str | None = None
    unit_type: str | None = None   # pcs/kg/L/pack
    unit_size: str | None = None   # "500ml", "1kg"
    mrp: float | None = None
    tax_rate: float | None = None  # GST %
    min_stock: int | None = None
    max_stock: int | None = None
    safety_stock: int | None = None
    reorder_qty: int | None = None
    supplier_id: str | None = None
    supplier_cost: float | None = None
    lead_time_days: int | None = None
    moq: int | None = None            # min order qty
    storage_type: str | None = None   # ambient/refrigerated/frozen
    shelf_location: str | None = None
    is_demo: int = 0  # 1 = seeded demo row


def sale_active(p: "Product") -> bool:
    return p.sale_price is not None and p.sale_price > 0 and (
        p.sale_ends is None or p.sale_ends >= date.today())


def effective_price(p: "Product") -> float:
    """What a customer pays right now: the active sale price, else the regular price."""
    return float(p.sale_price) if sale_active(p) else float(p.price)


class StockAdjustment(MongoModel):
    """Audit log of manual stock changes (deliveries received, damage, corrections)."""

    COLLECTION: ClassVar[str] = "stock_adjustments"

    business_id: str
    product_id: str
    product_name: str
    delta: int                 # +received / -removed
    reason: str = "correction"  # delivery | damaged | expired | theft | correction
    note: str = ""
    stock_after: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Employee(MongoModel):
    COLLECTION: ClassVar[str] = "employees"

    business_id: str
    name: str
    role: str = "Staff"
    salary: float = 18000.0
    department: str = "Operations"
    performance: float = 0.8  # 0..1


class Supplier(MongoModel):
    COLLECTION: ClassVar[str] = "suppliers"

    business_id: str
    name: str
    category: str = "General"
    reliability: float = 0.9  # 0..1
    lead_time_days: int = 3
    cost_index: float = 1.0  # 1.0 = market average


class DailyMetric(MongoModel):
    """One document per business per day — the historical heartbeat of the digital twin."""

    COLLECTION: ClassVar[str] = "daily_metrics"
    DATE_FIELDS: ClassVar[tuple[str, ...]] = ("day",)

    business_id: str
    day: date
    revenue: float = 0.0
    expenses: float = 0.0
    customers: int = 0
    orders: int = 0
    new_customers: int = 0
    inventory_value: float = 0.0


class ProductSale(MongoModel):
    """Daily units sold per product (for top-sellers / velocity analytics)."""

    COLLECTION: ClassVar[str] = "product_sales"
    DATE_FIELDS: ClassVar[tuple[str, ...]] = ("day",)

    business_id: str
    product_id: str
    day: date
    units: int = 0
    revenue: float = 0.0


class Scenario(MongoModel):
    COLLECTION: ClassVar[str] = "scenarios"

    business_id: str
    name: str
    levers_json: str = "{}"   # simulator inputs
    results_json: str = "{}"  # simulation outputs
    created_at: datetime = Field(default_factory=utcnow)


class ProductExperiment(MongoModel):
    """A virtual new-product launch experiment: test before you stock."""

    COLLECTION: ClassVar[str] = "product_experiments"

    business_id: str
    product_name: str
    brand: str = ""
    category: str = "General"
    subcategory: str = ""
    description: str = ""
    unit_type: str = "pcs"
    unit_size: str = ""

    # cost structure (per unit)
    supplier_cost: float = 0.0
    transport_cost: float = 0.0
    storage_cost: float = 0.0
    handling_cost: float = 0.0
    other_variable_cost: float = 0.0
    wastage_percent: float = 0.0
    tax_rate: float = 0.0

    # price experiment range
    min_price: float = 0.0
    max_price: float = 0.0
    price_step: float = 1.0
    planned_price: float = 0.0

    # launch plan
    discount_percent: float = 0.0
    initial_stock: int = 100
    safety_stock: int = 0
    reorder_point: int = 0
    supplier_lead_time: int = 3
    marketing_budget: float = 0.0
    launch_date: str = ""
    target_segment: str = "All Customers"
    shelf_placement: str = "Middle Shelf"
    competitor_price: float = 0.0  # 0 = not provided

    status: str = "draft"  # draft|simulated|decided
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)  # $set explicitly on update


class ProductExperimentScenario(MongoModel):
    """A saved launch strategy for an experiment (price/discount/stock/marketing combo)."""

    COLLECTION: ClassVar[str] = "product_experiment_scenarios"

    experiment_id: str
    name: str
    price: float
    discount: float = 0.0
    stock: int = 100
    marketing_budget: float = 0.0
    assumptions_json: str = "{}"
    results_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)


class ChatMessage(MongoModel):
    COLLECTION: ClassVar[str] = "chat_messages"

    business_id: str
    role: str  # user | assistant
    content: str
    created_at: datetime = Field(default_factory=utcnow)


class Bill(MongoModel):
    """A point-of-sale bill. Creating one decrements stock and feeds the day's
    real sales into the twin (product_sales + daily_metrics)."""

    COLLECTION: ClassVar[str] = "bills"
    DATE_FIELDS: ClassVar[tuple[str, ...]] = ("day",)

    business_id: str
    bill_no: str
    status: str = "paid"  # paid | cancelled
    customer_name: str = ""
    customer_phone: str = ""
    payment_method: str = "cash"  # cash | upi | card
    # line items: {product_id, name, qty, unit_price, tax_rate, line_total}
    items: list[dict] = Field(default_factory=list)
    subtotal: float = 0.0
    discount_pct: float = 0.0
    discount_amount: float = 0.0
    total: float = 0.0
    tax_included: float = 0.0     # informational: GST portion inside the total
    counted_new_customer: int = 0  # 1 if this bill's phone was seen for the first time
    day: date
    created_at: datetime = Field(default_factory=utcnow)


class Decision(MongoModel):
    """AI CEO Mode: a proposed action awaiting the owner's approval."""

    COLLECTION: ClassVar[str] = "decisions"

    business_id: str
    key: str            # dedupe key, e.g. "restock:<product_id>"
    kind: str           # restock | price | clearance | marketing | spending
    title: str
    detail: str
    expected_impact: str
    impact_inr: float = 0.0
    action_type: str = "advice"   # update_price | log_order | advice
    action_json: str = "{}"       # payload for apply on approval
    status: str = "pending"       # pending | approved | rejected
    result_note: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    decided_at: datetime | None = None
