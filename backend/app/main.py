from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import DuplicateKeyError

from .config import settings
from .database import ensure_indexes, get_db
from .models import Business, User, insert_model
from .routers import (analytics, auth, business, data_center, experiments,
                      insights_router, intel, products, simulate)
from .security import hash_password
from .seed import seed_business

app = FastAPI(title="TwinBiz AI", description="AI-Powered Digital Twin Platform for SMEs", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_origin_regex=r"^https://twin-biz-ai\.vercel\.app$|^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(business.router)
app.include_router(products.router)
app.include_router(data_center.router)
app.include_router(experiments.router)
app.include_router(analytics.router)
app.include_router(simulate.router)
app.include_router(insights_router.router)
app.include_router(intel.router)


@app.get("/api/healthz")
def healthz():
    return {"status": "ok", "app": settings.app_name}


@app.on_event("startup")
def startup():
    db = get_db()
    ensure_indexes(db)
    _ensure_demo_account()


def _ensure_demo_account():
    """Seed a demo login so judges can explore instantly: demo@twinbiz.ai / demo1234."""
    db = get_db()
    if db.users.find_one({"email": "demo@twinbiz.ai"}):
        return
    user = User(email="demo@twinbiz.ai", full_name="Demo Owner",
                password_hash=hash_password("demo1234"))
    try:
        insert_model(db, user)
    except DuplicateKeyError:
        return  # another worker seeded concurrently
    biz = Business(
        owner_id=user.id, name="SmartMart Supermarket", business_type="Supermarket",
        location="Hyderabad, Telangana", employees_count=8, monthly_revenue=850000,
        monthly_expenses=690000, customer_count=2400, working_hours="8:00-22:00",
    )
    insert_model(db, biz)
    seed_business(db, biz)
