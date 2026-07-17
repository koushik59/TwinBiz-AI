"""Billing / POS API: create bills, list history, download PDF invoices, cancel."""

import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo.database import Database

from ..database import get_db, oid
from ..models import Bill, Business, find_models
from ..security import get_current_business
from ..services import billing

router = APIRouter(prefix="/api/billing", tags=["billing"])


class BillItemIn(BaseModel):
    product_id: str
    qty: int = Field(ge=1)


class BillIn(BaseModel):
    items: list[BillItemIn]
    customer_name: str = ""
    customer_phone: str = ""
    payment_method: str = "cash"
    discount_pct: float = Field(default=0, ge=0, le=90)


def _bill_out(b: Bill) -> dict:
    return {
        "id": b.id, "bill_no": b.bill_no, "status": b.status,
        "customer_name": b.customer_name, "customer_phone": b.customer_phone,
        "payment_method": b.payment_method, "items": b.items,
        "subtotal": b.subtotal, "discount_pct": b.discount_pct,
        "discount_amount": b.discount_amount, "total": b.total,
        "tax_included": b.tax_included, "day": b.day.isoformat(),
        "created_at": b.created_at.isoformat(),
    }


def _get_bill(db: Database, business: Business, bill_id: str) -> Bill:
    doc = db.bills.find_one({"_id": oid(bill_id), "business_id": business.id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bill not found")
    return Bill.from_doc(doc)


@router.post("/bills")
def create_bill(body: BillIn, business: Business = Depends(get_current_business),
                db: Database = Depends(get_db)):
    try:
        bill = billing.create_bill(
            db, business, items=[i.model_dump() for i in body.items],
            customer_name=body.customer_name, customer_phone=body.customer_phone,
            payment_method=body.payment_method, discount_pct=body.discount_pct)
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _bill_out(bill)


@router.get("/bills")
def list_bills(limit: int = Query(30, ge=1, le=100),
               business: Business = Depends(get_current_business),
               db: Database = Depends(get_db)):
    rows = find_models(db, Bill, {"business_id": business.id},
                       sort=[("created_at", -1)], limit=limit)
    today = [b for b in rows if b.status == "paid" and b.day == date.today()]
    return {
        "items": [_bill_out(b) for b in rows],
        "summary": {
            "today_bills": len(today),
            "today_revenue": round(sum(b.total for b in today), 2),
        },
    }


@router.get("/bills/{bill_id}")
def get_bill(bill_id: str, business: Business = Depends(get_current_business),
             db: Database = Depends(get_db)):
    return _bill_out(_get_bill(db, business, bill_id))


@router.get("/bills/{bill_id}/pdf")
def bill_pdf(bill_id: str, business: Business = Depends(get_current_business),
             db: Database = Depends(get_db)):
    bill = _get_bill(db, business, bill_id)
    pdf = billing.bill_pdf(business, bill)
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{bill.bill_no}.pdf"'},
    )


@router.post("/bills/{bill_id}/cancel")
def cancel_bill(bill_id: str, business: Business = Depends(get_current_business),
                db: Database = Depends(get_db)):
    bill = _get_bill(db, business, bill_id)
    try:
        return _bill_out(billing.cancel_bill(db, business, bill))
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
