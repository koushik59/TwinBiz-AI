from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Business, User
from .routers import analytics, auth, business, insights_router, simulate
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
app.include_router(analytics.router)
app.include_router(simulate.router)
app.include_router(insights_router.router)


@app.get("/api/healthz")
def healthz():
    return {"status": "ok", "app": settings.app_name}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _ensure_demo_account()


def _ensure_demo_account():
    """Seed a demo login so judges can explore instantly: demo@twinbiz.ai / demo1234."""
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == "demo@twinbiz.ai").first():
            return
        user = User(email="demo@twinbiz.ai", full_name="Demo Owner",
                    password_hash=hash_password("demo1234"))
        db.add(user)
        db.commit()
        db.refresh(user)
        biz = Business(
            owner_id=user.id, name="FreshMart Supermarket", business_type="Supermarket",
            location="Hyderabad, Telangana", employees_count=8, monthly_revenue=850000,
            monthly_expenses=690000, customer_count=2400, working_hours="8:00-22:00",
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)
        seed_business(db, biz)
    finally:
        db.close()
