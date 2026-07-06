import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, ChatMessage, DailyMetric
from ..security import get_current_business
from ..services.gemini import ask_gemini
from ..services.insights import build_alerts, compute_kpis, detect_risks, health_score, recommendations

router = APIRouter(prefix="/api/insights", tags=["insights"])


class ChatIn(BaseModel):
    message: str


@router.get("/risks")
def risks(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    return {"risks": detect_risks(db, business)}


@router.get("/recommendations")
def recs(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    return {"recommendations": recommendations(db, business)}


@router.get("/alerts")
def alerts(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    return {"alerts": build_alerts(db, business)}


@router.get("/health")
def health(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    return health_score(db, business)


@router.post("/advisor")
async def advisor(body: ChatIn, business: Business = Depends(get_current_business),
                  db: Session = Depends(get_db)):
    kpis = compute_kpis(db, business)
    biz_risks = detect_risks(db, business)
    recs_list = recommendations(db, business)
    context = {
        "business": {
            "name": business.name, "type": business.business_type, "location": business.location,
            "employees_count": business.employees_count, "working_hours": business.working_hours,
        },
        "kpis": kpis,
        "health": health_score(db, business),
        "risks": biz_risks[:5],
        "top_recommendation": recs_list[0]["title"] if recs_list else None,
    }
    db.add(ChatMessage(business_id=business.id, role="user", content=body.message))
    result = await ask_gemini(body.message, context)
    db.add(ChatMessage(business_id=business.id, role="assistant", content=result["answer"]))
    db.commit()
    return result


@router.get("/advisor/history")
def advisor_history(business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    msgs = (
        db.query(ChatMessage).filter(ChatMessage.business_id == business.id)
        .order_by(ChatMessage.created_at.desc()).limit(40).all()
    )
    return {"messages": [{"role": m.role, "content": m.content} for m in reversed(msgs)]}


@router.get("/report")
def report(period: str = "monthly", business: Business = Depends(get_current_business),
           db: Session = Depends(get_db)):
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 30)
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(DailyMetric)
        .filter(DailyMetric.business_id == business.id, DailyMetric.day >= since)
        .order_by(DailyMetric.day).all()
    )
    rev = sum(r.revenue for r in rows)
    exp = sum(r.expenses for r in rows)
    return {
        "period": period,
        "business": business.name,
        "generated": date.today().isoformat(),
        "summary": {
            "revenue": round(rev, 0), "expenses": round(exp, 0), "profit": round(rev - exp, 0),
            "customers": sum(r.customers for r in rows), "orders": sum(r.orders for r in rows),
            "margin_pct": round((rev - exp) / rev * 100, 1) if rev else 0,
        },
        "health": health_score(db, business),
        "risks": detect_risks(db, business),
        "recommendations": recommendations(db, business),
        "daily": [
            {"day": r.day.isoformat(), "revenue": r.revenue, "expenses": r.expenses,
             "profit": round(r.revenue - r.expenses, 0), "customers": r.customers, "orders": r.orders}
            for r in rows
        ],
    }


@router.get("/report/csv")
def report_csv(period: str = "monthly", business: Business = Depends(get_current_business),
               db: Session = Depends(get_db)):
    days = {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}.get(period, 30)
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(DailyMetric)
        .filter(DailyMetric.business_id == business.id, DailyMetric.day >= since)
        .order_by(DailyMetric.day).all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "revenue", "expenses", "profit", "customers", "orders"])
    for r in rows:
        writer.writerow([r.day.isoformat(), r.revenue, r.expenses,
                         round(r.revenue - r.expenses, 0), r.customers, r.orders])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=twinbiz_{period}_report.csv"},
    )
