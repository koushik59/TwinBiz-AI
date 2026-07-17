"""Billing / point-of-sale engine.

Every bill is a real transaction flowing into the twin:
  - product stock is decremented,
  - the day's per-product sales (product_sales) are incremented,
  - the day's business metrics (daily_metrics: revenue, orders, customers,
    new_customers) are incremented,
  - the business data source flips demo -> mixed (real data has arrived).

Cancelling a bill reverses exactly what it applied. PDF invoices are generated
server-side with fpdf2 (amounts printed as "Rs." — the built-in PDF fonts have
no ₹ glyph).
"""

from datetime import date

from fpdf import FPDF
from pymongo.database import Database

from ..database import next_seq, oid
from ..models import Bill, Business, Product, effective_price, insert_model, to_dt


class BillingError(ValueError):
    """User-facing validation problem (maps to HTTP 400)."""


def _metrics_inc(db: Database, business_id: str, day: date, *, revenue: float,
                 orders: int, customers: int, new_customers: int) -> None:
    db.daily_metrics.update_one(
        {"business_id": business_id, "day": to_dt(day)},
        {"$inc": {"revenue": revenue, "orders": orders,
                  "customers": customers, "new_customers": new_customers},
         "$setOnInsert": {"expenses": 0.0, "inventory_value": 0.0}},
        upsert=True,
    )


def create_bill(db: Database, business: Business, *, items: list[dict],
                customer_name: str = "", customer_phone: str = "",
                payment_method: str = "cash", discount_pct: float = 0.0) -> Bill:
    """items: [{product_id, qty}]. Prices and totals come from the catalog."""
    if not items:
        raise BillingError("Add at least one product to the bill")
    if not 0 <= discount_pct <= 90:
        raise BillingError("Discount must be between 0 and 90%")

    # resolve products and validate stock first — fail before touching anything
    lines: list[dict] = []
    for it in items:
        qty = int(it.get("qty", 0))
        if qty <= 0:
            raise BillingError("Quantities must be at least 1")
        doc = db.products.find_one({"_id": oid(str(it.get("product_id"))),
                                    "business_id": business.id})
        if not doc:
            raise BillingError("A product on this bill no longer exists")
        p = Product.from_doc(doc)
        if p.stock < qty:
            raise BillingError(f"Only {p.stock} units of {p.name} in stock (bill asks for {qty})")
        unit = effective_price(p)  # charges the temporary sale price while one is active
        lines.append({
            "product_id": p.id, "name": p.name, "qty": qty,
            "unit_price": round(unit, 2), "tax_rate": p.tax_rate or 0.0,
            "line_total": round(unit * qty, 2),
        })

    subtotal = round(sum(l["line_total"] for l in lines), 2)
    discount_amount = round(subtotal * discount_pct / 100.0, 2)
    total = round(subtotal - discount_amount, 2)
    # catalog prices are MRP-style tax-inclusive; surface the GST portion for info
    tax_included = round(sum(
        l["line_total"] * (l["tax_rate"] / (100.0 + l["tax_rate"]))
        for l in lines if l["tax_rate"]) * (1 - discount_pct / 100.0), 2)

    # first time we've seen this phone number -> a new customer for the twin
    phone = customer_phone.strip()
    is_new_customer = bool(phone) and db.bills.find_one(
        {"business_id": business.id, "customer_phone": phone, "status": "paid"}) is None

    bill = Bill(
        business_id=business.id,
        bill_no=f"INV-{next_seq(db, f'bill:{business.id}'):05d}",
        customer_name=customer_name.strip(), customer_phone=phone,
        payment_method=payment_method if payment_method in ("cash", "upi", "card") else "cash",
        items=lines, subtotal=subtotal, discount_pct=discount_pct,
        discount_amount=discount_amount, total=total, tax_included=tax_included,
        counted_new_customer=1 if is_new_customer else 0,
        day=date.today(),
    )
    insert_model(db, bill)

    # --- feed the twin -----------------------------------------------------
    for l in lines:
        db.products.update_one({"_id": oid(l["product_id"])},
                               {"$inc": {"stock": -l["qty"]}})
        share = l["line_total"] / subtotal if subtotal else 0
        db.product_sales.update_one(
            {"business_id": business.id, "product_id": l["product_id"], "day": to_dt(bill.day)},
            {"$inc": {"units": l["qty"], "revenue": round(l["line_total"] - discount_amount * share, 2)}},
            upsert=True,
        )
    _metrics_inc(db, business.id, bill.day, revenue=total, orders=1,
                 customers=1, new_customers=bill.counted_new_customer)
    if business.data_source == "demo":
        db.businesses.update_one({"_id": oid(business.id)}, {"$set": {"data_source": "mixed"}})
        business.data_source = "mixed"
    return bill


def cancel_bill(db: Database, business: Business, bill: Bill) -> Bill:
    if bill.status == "cancelled":
        raise BillingError("This bill is already cancelled")
    subtotal = bill.subtotal or 1
    for l in bill.items:
        db.products.update_one({"_id": oid(l["product_id"])},
                               {"$inc": {"stock": l["qty"]}})
        share = l["line_total"] / subtotal
        db.product_sales.update_one(
            {"business_id": business.id, "product_id": l["product_id"], "day": to_dt(bill.day)},
            {"$inc": {"units": -l["qty"],
                      "revenue": -round(l["line_total"] - bill.discount_amount * share, 2)}},
        )
    _metrics_inc(db, business.id, bill.day, revenue=-bill.total, orders=-1,
                 customers=-1, new_customers=-bill.counted_new_customer)
    db.bills.update_one({"_id": oid(bill.id)}, {"$set": {"status": "cancelled"}})
    return bill.model_copy(update={"status": "cancelled"})


# ---------------------------------------------------------------------------
# PDF invoice
# ---------------------------------------------------------------------------

def _rs(amount: float) -> str:
    return f"Rs. {amount:,.2f}"


def bill_pdf(business: Business, bill: Bill) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # header
    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(109, 93, 246)
    pdf.cell(0, 10, business.name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(110, 116, 138)
    if business.location:
        pdf.cell(0, 5, business.location, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Powered by TwinBiz AI", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # bill meta
    pdf.set_text_color(26, 34, 51)
    pdf.set_font("helvetica", "B", 13)
    status = "  (CANCELLED)" if bill.status == "cancelled" else ""
    pdf.cell(0, 8, f"Invoice {bill.bill_no}{status}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 5, f"Date: {bill.day.strftime('%d %b %Y')}    Payment: {bill.payment_method.upper()}",
             new_x="LMARGIN", new_y="NEXT")
    if bill.customer_name or bill.customer_phone:
        who = bill.customer_name or "Customer"
        phone = f"  ({bill.customer_phone})" if bill.customer_phone else ""
        pdf.cell(0, 5, f"Billed to: {who}{phone}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # items table
    col_w = (92, 20, 34, 34)  # name, qty, price, total
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(242, 240, 254)
    for text, w, align in zip(("Item", "Qty", "Unit Price", "Amount"), col_w, ("L", "C", "R", "R")):
        pdf.cell(w, 8, text, border="B", align=align, fill=True)
    pdf.ln()
    pdf.set_font("helvetica", "", 9)
    for l in bill.items:
        pdf.cell(col_w[0], 7, str(l["name"])[:52], border="B")
        pdf.cell(col_w[1], 7, str(l["qty"]), border="B", align="C")
        pdf.cell(col_w[2], 7, _rs(l["unit_price"]), border="B", align="R")
        pdf.cell(col_w[3], 7, _rs(l["line_total"]), border="B", align="R")
        pdf.ln()

    # totals
    pdf.ln(3)
    def total_row(label: str, value: str, bold: bool = False):
        pdf.set_font("helvetica", "B" if bold else "", 10 if bold else 9)
        pdf.cell(col_w[0] + col_w[1], 7, "")
        pdf.cell(col_w[2], 7, label, align="R")
        pdf.cell(col_w[3], 7, value, align="R")
        pdf.ln()

    total_row("Subtotal", _rs(bill.subtotal))
    if bill.discount_amount:
        total_row(f"Discount ({bill.discount_pct:g}%)", f"- {_rs(bill.discount_amount)}")
    total_row("TOTAL", _rs(bill.total), bold=True)
    if bill.tax_included:
        pdf.set_font("helvetica", "I", 8)
        pdf.set_text_color(110, 116, 138)
        pdf.cell(0, 6, f"Includes GST of {_rs(bill.tax_included)} (prices are tax-inclusive)",
                 align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)
    pdf.set_font("helvetica", "I", 9)
    pdf.set_text_color(110, 116, 138)
    pdf.cell(0, 6, "Thank you for your business!", align="C", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
