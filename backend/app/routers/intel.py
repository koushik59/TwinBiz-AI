"""Intelligence API: DNA, mood, weather, stress tests, time machine,
opportunity radar, future news and the AI CEO decision inbox."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from ..database import get_db
from ..models import Business
from ..security import get_current_business
from ..services import ceo, stress_test, time_machine
from ..services.intelligence import (business_dna, business_weather, future_news,
                                     opportunity_radar)

router = APIRouter(prefix="/api/intel", tags=["intelligence"])


@router.get("/dna")
def dna(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return business_dna(db, business)


@router.get("/weather")
def weather(days: int = 7, business: Business = Depends(get_current_business),
            db: Database = Depends(get_db)):
    return business_weather(db, business, days)


@router.get("/stress-tests")
def stress_tests(business: Business = Depends(get_current_business),
                 db: Database = Depends(get_db)):
    return stress_test.run_all(db, business)


@router.get("/time-machine")
def time_machine_replay(date_str: str = Query("", alias="date"),
                        business: Business = Depends(get_current_business),
                        db: Database = Depends(get_db)):
    try:
        on_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    return time_machine.replay(db, business, on_date)


@router.get("/opportunities")
def opportunities(business: Business = Depends(get_current_business),
                  db: Database = Depends(get_db)):
    return opportunity_radar(db, business)


@router.get("/future-news")
def news(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return future_news(db, business)


@router.get("/decisions")
def decisions(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    return ceo.list_decisions(db, business)


@router.post("/decisions/{decision_id}/approve")
def approve_decision(decision_id: str, business: Business = Depends(get_current_business),
                     db: Database = Depends(get_db)):
    result = ceo.decide(db, business, decision_id, approve=True)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/decisions/{decision_id}/reject")
def reject_decision(decision_id: str, business: Business = Depends(get_current_business),
                    db: Database = Depends(get_db)):
    result = ceo.decide(db, business, decision_id, approve=False)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
