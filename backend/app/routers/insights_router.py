import csv
import io
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pymongo.database import Database

from ..database import get_db
from ..models import (Business, ChatMessage, DailyMetric, ProductExperiment,
                      Scenario, find_models, to_dt)
from ..security import get_current_business
from ..services.forecasting import forecast_series
from ..services.gemini import ask_gemini
from ..services.insights import (build_alerts, compute_kpis, detect_risks, health_score,
                                 recommendations, twin_status)

router = APIRouter(prefix="/api/insights", tags=["insights"])


class ChatIn(BaseModel):
    message: str


@router.get("/risks")
def risks(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return {"risks": detect_risks(db, business)}


@router.get("/recommendations")
def recs(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return {"recommendations": recommendations(db, business)}


@router.get("/alerts")
def alerts(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return {"alerts": build_alerts(db, business)}


@router.get("/health")
def health(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return health_score(db, business)


@router.post("/advisor")
async def advisor(body: ChatIn, business: Business = Depends(get_current_business),
                  db: Database = Depends(get_db)):
    kpis = compute_kpis(db, business)
    biz_risks = detect_risks(db, business)
    recs_list = recommendations(db, business)

    # forecast summary so the advisor can talk about the future with real numbers
    since = to_dt(date.today() - timedelta(days=180))
    rows = find_models(db, DailyMetric,
                       {"business_id": business.id, "day": {"$gte": since}},
                       sort=[("day", 1)])
    fc = forecast_series([(r.day, r.revenue) for r in rows], 30)
    forecast_summary = {
        "next_30d_revenue": round(sum(p["value"] for p in fc.get("forecast", [])), 0),
        "trend_pct_per_month": fc.get("trend_pct_per_month"),
        "model_confidence_pct": fc.get("confidence"),
    } if fc.get("forecast") else None

    scenarios = find_models(db, Scenario, {"business_id": business.id},
                            sort=[("created_at", -1)], limit=4)
    experiments = find_models(db, ProductExperiment, {"business_id": business.id},
                              sort=[("created_at", -1)], limit=4)

    context = {
        "business": {
            "name": business.name, "type": business.business_type, "location": business.location,
            "employees_count": business.employees_count, "working_hours": business.working_hours,
        },
        "twin_status": twin_status(db, business),
        "kpis": kpis,
        "health": health_score(db, business),
        "risks": biz_risks[:5],
        "top_recommendation": recs_list[0]["title"] if recs_list else None,
        "forecast": forecast_summary,
        "saved_scenarios": [
            {"name": s.name, "predicted_profit": json.loads(s.results_json).get("profit")}
            for s in scenarios
        ],
        "product_experiments": [
            {"name": e.product_name, "category": e.category, "planned_price": e.planned_price,
             "status": e.status, "hint": "details live in the Product Launch Lab"}
            for e in experiments
        ],
    }
    db.chat_messages.insert_one(
        ChatMessage(business_id=business.id, role="user", content=body.message).to_doc())
    result = await ask_gemini(body.message, context)
    db.chat_messages.insert_one(
        ChatMessage(business_id=business.id, role="assistant", content=result["answer"]).to_doc())
    return result


@router.get("/advisor/history")
def advisor_history(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    msgs = find_models(db, ChatMessage, {"business_id": business.id},
                       sort=[("created_at", -1)], limit=40)
    return {"messages": [{"role": m.role, "content": m.content} for m in reversed(msgs)]}


@router.get("/report")
def report(period: str = "monthly", business: Business = Depends(get_current_business),
           db: Database = Depends(get_db)):
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 30)
    since = to_dt(date.today() - timedelta(days=days))
    rows = find_models(db, DailyMetric,
                       {"business_id": business.id, "day": {"$gte": since}},
                       sort=[("day", 1)])
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
               db: Database = Depends(get_db)):
    days = {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}.get(period, 30)
    since = to_dt(date.today() - timedelta(days=days))
    rows = find_models(db, DailyMetric,
                       {"business_id": business.id, "day": {"$gte": since}},
                       sort=[("day", 1)])
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
