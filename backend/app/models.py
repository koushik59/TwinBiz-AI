from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(50), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    businesses: Mapped[list["Business"]] = relationship(back_populates="owner")


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    business_type: Mapped[str] = mapped_column(String(100), default="Supermarket")
    location: Mapped[str] = mapped_column(String(255), default="")
    employees_count: Mapped[int] = mapped_column(Integer, default=5)
    monthly_revenue: Mapped[float] = mapped_column(Float, default=500000.0)
    monthly_expenses: Mapped[float] = mapped_column(Float, default=380000.0)
    customer_count: Mapped[int] = mapped_column(Integer, default=1200)
    working_hours: Mapped[str] = mapped_column(String(50), default="9:00-21:00")
    currency: Mapped[str] = mapped_column(String(10), default="₹")
    # "demo" = seeded synthetic history, "real" = user data, "mixed" = both
    data_source: Mapped[str] = mapped_column(String(20), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner: Mapped[User] = relationship(back_populates="businesses")
    products: Mapped[list["Product"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    employees: Mapped[list["Employee"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    suppliers: Mapped[list["Supplier"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    daily_metrics: Mapped[list["DailyMetric"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    scenarios: Mapped[list["Scenario"]] = relationship(back_populates="business", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="General")
    price: Mapped[float] = mapped_column(Float, default=100.0)   # current selling price
    cost: Mapped[float] = mapped_column(Float, default=70.0)     # cost price
    stock: Mapped[int] = mapped_column(Integer, default=100)
    reorder_level: Mapped[int] = mapped_column(Integer, default=30)  # reorder point
    daily_demand: Mapped[float] = mapped_column(Float, default=10.0)
    expiry_days: Mapped[int] = mapped_column(Integer, default=0)  # shelf life; 0 = non-perishable

    # -- extended catalog fields (nullable → additive SQLite migration) ------
    sku: Mapped[str | None] = mapped_column(String(64), default=None)
    barcode: Mapped[str | None] = mapped_column(String(64), default=None)
    brand: Mapped[str | None] = mapped_column(String(100), default=None)
    subcategory: Mapped[str | None] = mapped_column(String(100), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    unit_type: Mapped[str | None] = mapped_column(String(30), default=None)   # pcs/kg/L/pack
    unit_size: Mapped[str | None] = mapped_column(String(50), default=None)   # "500ml", "1kg"
    mrp: Mapped[float | None] = mapped_column(Float, default=None)
    tax_rate: Mapped[float | None] = mapped_column(Float, default=None)       # GST %
    min_stock: Mapped[int | None] = mapped_column(Integer, default=None)
    max_stock: Mapped[int | None] = mapped_column(Integer, default=None)
    safety_stock: Mapped[int | None] = mapped_column(Integer, default=None)
    reorder_qty: Mapped[int | None] = mapped_column(Integer, default=None)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), default=None)
    supplier_cost: Mapped[float | None] = mapped_column(Float, default=None)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, default=None)
    moq: Mapped[int | None] = mapped_column(Integer, default=None)            # min order qty
    storage_type: Mapped[str | None] = mapped_column(String(50), default=None)  # ambient/refrigerated/frozen
    shelf_location: Mapped[str | None] = mapped_column(String(80), default=None)
    is_demo: Mapped[int] = mapped_column(Integer, default=0)  # 1 = seeded demo row

    business: Mapped[Business] = relationship(back_populates="products")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(100), default="Staff")
    salary: Mapped[float] = mapped_column(Float, default=18000.0)
    department: Mapped[str] = mapped_column(String(100), default="Operations")
    performance: Mapped[float] = mapped_column(Float, default=0.8)  # 0..1

    business: Mapped[Business] = relationship(back_populates="employees")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="General")
    reliability: Mapped[float] = mapped_column(Float, default=0.9)  # 0..1
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3)
    cost_index: Mapped[float] = mapped_column(Float, default=1.0)  # 1.0 = market average

    business: Mapped[Business] = relationship(back_populates="suppliers")


class DailyMetric(Base):
    """One row per business per day — the historical heartbeat of the digital twin."""

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    expenses: Mapped[float] = mapped_column(Float, default=0.0)
    customers: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    new_customers: Mapped[int] = mapped_column(Integer, default=0)
    inventory_value: Mapped[float] = mapped_column(Float, default=0.0)

    business: Mapped[Business] = relationship(back_populates="daily_metrics")


class ProductSale(Base):
    """Daily units sold per product (for top-sellers / velocity analytics)."""

    __tablename__ = "product_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    units: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    levers_json: Mapped[str] = mapped_column(Text, default="{}")   # simulator inputs
    results_json: Mapped[str] = mapped_column(Text, default="{}")  # simulation outputs
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    business: Mapped[Business] = relationship(back_populates="scenarios")


class ProductExperiment(Base):
    """A virtual new-product launch experiment: test before you stock (§15-34)."""

    __tablename__ = "product_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str] = mapped_column(String(100), default="")
    category: Mapped[str] = mapped_column(String(100), default="General")
    subcategory: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    unit_type: Mapped[str] = mapped_column(String(30), default="pcs")
    unit_size: Mapped[str] = mapped_column(String(50), default="")

    # cost structure (per unit)
    supplier_cost: Mapped[float] = mapped_column(Float, default=0.0)
    transport_cost: Mapped[float] = mapped_column(Float, default=0.0)
    storage_cost: Mapped[float] = mapped_column(Float, default=0.0)
    handling_cost: Mapped[float] = mapped_column(Float, default=0.0)
    other_variable_cost: Mapped[float] = mapped_column(Float, default=0.0)
    wastage_percent: Mapped[float] = mapped_column(Float, default=0.0)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # price experiment range
    min_price: Mapped[float] = mapped_column(Float, default=0.0)
    max_price: Mapped[float] = mapped_column(Float, default=0.0)
    price_step: Mapped[float] = mapped_column(Float, default=1.0)
    planned_price: Mapped[float] = mapped_column(Float, default=0.0)

    # launch plan
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    initial_stock: Mapped[int] = mapped_column(Integer, default=100)
    safety_stock: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    supplier_lead_time: Mapped[int] = mapped_column(Integer, default=3)
    marketing_budget: Mapped[float] = mapped_column(Float, default=0.0)
    launch_date: Mapped[str] = mapped_column(String(20), default="")
    target_segment: Mapped[str] = mapped_column(String(60), default="All Customers")
    shelf_placement: Mapped[str] = mapped_column(String(60), default="Middle Shelf")
    competitor_price: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = not provided

    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft|simulated|decided
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    scenarios: Mapped[list["ProductExperimentScenario"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan")


class ProductExperimentScenario(Base):
    """A saved launch strategy for an experiment (price/discount/stock/marketing combo)."""

    __tablename__ = "product_experiment_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("product_experiments.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=100)
    marketing_budget: Mapped[float] = mapped_column(Float, default=0.0)
    assumptions_json: Mapped[str] = mapped_column(Text, default="{}")
    results_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    experiment: Mapped[ProductExperiment] = relationship(back_populates="scenarios")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
