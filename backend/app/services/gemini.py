"""AI Business Advisor.

Talks to the Gemini API when GEMINI_API_KEY is set; otherwise falls back to a
context-aware rule-based advisor so the demo works fully offline. Either way,
the advisor is grounded in the business's live twin data (KPIs, risks, health).
"""

import json
import logging

import httpx

from ..config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are TwinBiz AI, an expert business advisor embedded in a digital-twin
platform for small businesses. You are given the live state of the user's business
(KPIs, health score, detected risks, top products). Answer the owner's question with:
1. A clear explanation grounded in their numbers,
2. A prediction of what will happen,
3. A concrete recommendation,
4. Key risk to watch,
5. A confidence level (High/Medium/Low).
Be concise (under 220 words), use the ₹ currency, and format with short markdown sections."""


async def ask_gemini(question: str, context: dict) -> dict:
    if settings.gemini_api_key:
        try:
            return await _call_gemini(question, context)
        except Exception as exc:
            log.warning("Gemini API call failed (%s): %s — falling back to twin-engine", type(exc).__name__, exc)
    return _fallback_answer(question, context)


async def _call_gemini(question: str, context: dict) -> dict:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "LIVE BUSINESS STATE:\n"
                        + json.dumps(context, indent=1, default=str)
                        + f"\n\nOWNER'S QUESTION: {question}"
                    }
                ],
            }
        ],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return {"answer": text, "source": "gemini", "confidence": "High"}


# ---------------------------------------------------------------------------
# Fallback advisor — deterministic, grounded in the twin's real numbers
# ---------------------------------------------------------------------------

def _fallback_answer(question: str, ctx: dict) -> dict:
    """Context-aware rule-based advisor grounded in the twin's real numbers."""
    q = question.lower()
    kpis = ctx.get("kpis", {})
    risks = ctx.get("risks", [])
    health = ctx.get("health", {})
    pillars = health.get("pillars", {})
    biz = ctx.get("business", {})

    rev = kpis.get("monthly_revenue", 0)
    profit = kpis.get("monthly_profit", 0)
    margin = kpis.get("profit_margin_pct", 0)
    rev_chg = kpis.get("revenue_change_pct", 0)
    exp = kpis.get("monthly_expenses", 0)
    exp_chg = kpis.get("expense_change_pct", 0)
    customers = kpis.get("monthly_customers", 0)
    cust_chg = kpis.get("customer_change_pct", 0)
    inv_value = kpis.get("inventory_value", 0)
    overall_health = health.get("overall", 50)
    top_risk = risks[0]["title"] if risks else "no critical risk detected"
    top_rec = ctx.get("top_recommendation", "Run a simulation to explore your best next move.")

    def fmt(n):
        return f"₹{n:,.0f}"

    # --- 1. Price increase / raise prices ---
    if _match(q, ["price"], ["increase", "raise", "higher", "hike", "up"]):
        answer = (
            f"**Explanation** — Your current margin is {margin}% on {fmt(rev)}/month. Demand in your "
            f"segment is price-sensitive, so a price rise trades volume for margin.\n\n"
            f"**Prediction** — A 5% increase typically drops demand ~7–9% here, netting **+2–3% profit** "
            f"but −5% footfall. Beyond 10% the curve turns negative.\n\n"
            f"**Recommendation** — Raise prices 3–5% only on low-elasticity items (essentials, exclusives); "
            f"keep traffic-driver prices flat. Test in the Simulator first.\n\n"
            f"**Risk** — Customer churn if competitors hold prices.\n\n**Confidence:** Medium-High"
        )
        confidence = "Medium"

    # --- 2. Price decrease / lower prices ---
    elif _match(q, ["price"], ["decrease", "reduce", "lower", "drop", "cut"]):
        answer = (
            f"**Explanation** — Cutting prices boosts footfall via price elasticity. Your current margin "
            f"is {margin}%, giving you {'some' if margin > 10 else 'very limited'} room to absorb a cut.\n\n"
            f"**Prediction** — A 5% cut typically lifts demand 8–12% in your category. Net profit may "
            f"{'stay flat' if margin > 15 else 'dip'} depending on volume uplift.\n\n"
            f"**Recommendation** — {'Test a 5% cut on 3–4 traffic-driver SKUs for 2 weeks.' if margin > 10 else 'Your margin is too thin for broad cuts. Try bundled offers or selective loss-leaders instead.'}\n\n"
            f"**Risk** — Margin erosion if volume doesn't compensate.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 3. Hiring / staffing ---
    elif _match(q, ["hire", "employee", "staff", "recruit", "workforce", "manpower"]):
        emp_count = biz.get("employees_count", "several")
        answer = (
            f"**Explanation** — You run {emp_count} staff against "
            f"{customers:,} customer visits/month. Service capacity directly drives "
            f"retention in your category.\n\n"
            f"**Prediction** — One extra hire (~₹18,000/month) shortens waits, lifting satisfaction ~4–6 pts and "
            f"revenue ~2–3% ({fmt(rev * 0.025)}). Net effect is positive if monthly profit stays above "
            f"{fmt(18000)} of headroom — yours is {fmt(profit)}.\n\n"
            f"**Recommendation** — {'Hire for peak hours (part-time first).' if profit > 40000 else 'Hold hiring; margin is too thin — fix profitability first.'}\n\n"
            f"**Risk** — Fixed cost if demand dips.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 4. Sales decline ---
    elif _match(q, ["sales", "revenue"], ["decrease", "drop", "down", "decline", "fall", "low", "slow", "why"]):
        answer = (
            f"**Explanation** — Revenue moved {rev_chg:+}% month-over-month. My risk scan flags: *{top_risk}*. "
            f"Sales dips usually trace to stockouts on fast movers, footfall decline, or seasonal cycles visible "
            f"in your trend chart.\n\n"
            f"**Prediction** — If untreated, the current trend compounds to ~{rev_chg * 2:+.0f}% over two months.\n\n"
            f"**Recommendation** — Check Inventory Intelligence for stockouts first (highest-frequency cause), "
            f"then run the 'Boost marketing' scenario in the Simulator.\n\n"
            f"**Risk** — Misreading seasonality as decline.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 5. Stock / inventory ---
    elif _match(q, ["stock", "inventory", "restock", "stockout", "warehouse"]):
        answer = (
            f"**Explanation** — Your inventory is worth {fmt(inv_value)}. The twin tracks "
            f"per-product velocity: fast movers deserve deeper stock, slow movers are frozen capital.\n\n"
            f"**Prediction** — Rebalancing stock toward your top-5 sellers typically lifts revenue 3–5% and cuts "
            f"carrying cost.\n\n"
            f"**Recommendation** — Open Inventory Intelligence → restock everything marked *critical*, and run a "
            f"clearance offer on items with >60 days of stock.\n\n"
            f"**Risk** — Supplier lead times during festivals.\n\n**Confidence:** High"
        )
        confidence = "High"

    # --- 6. Profit / margin improvement ---
    elif _match(q, ["profit", "margin", "earning", "bottom line", "net income"]):
        margin_status = "healthy" if margin > 12 else "thin" if margin > 5 else "dangerously low"
        answer = (
            f"**Explanation** — Your profit margin is **{margin}%** ({margin_status}). Monthly profit stands at "
            f"{fmt(profit)} on {fmt(rev)} revenue. The biggest levers are COGS reduction, waste minimization, "
            f"and selective price increases.\n\n"
            f"**Prediction** — A 5% reduction in supplier costs alone would add ~{fmt(exp * 0.55 * 0.05)}/month "
            f"straight to your bottom line.\n\n"
            f"**Recommendation** — {'Renegotiate your top-3 supplier contracts and cut slow-moving SKUs.' if margin < 12 else 'Margin is healthy — focus on revenue growth through marketing and hours extension.'}\n\n"
            f"**Risk** — Cutting costs too aggressively may hurt product quality or availability.\n\n**Confidence:** High"
        )
        confidence = "High"

    # --- 7. Marketing / advertising ---
    elif _match(q, ["marketing", "advertis", "promotion", "campaign", "social media", "ads", "brand"]):
        mkt_budget_est = exp * 0.05
        answer = (
            f"**Explanation** — Your estimated marketing spend is ~{fmt(mkt_budget_est)}/month (~5% of expenses). "
            f"In your business type, marketing has a diminishing-returns response curve — the first 50% boost "
            f"yields the highest ROI.\n\n"
            f"**Prediction** — Doubling your marketing budget typically lifts footfall 12–18% in your category, "
            f"translating to ~{fmt(rev * 0.15)} in additional revenue.\n\n"
            f"**Recommendation** — Start with local digital channels (Google My Business, WhatsApp broadcasts, "
            f"Instagram). Allocate 60% to digital, 40% to local flyers/banners. Run the 'Double marketing' "
            f"scenario in the Simulator to see the exact projection.\n\n"
            f"**Risk** — Diminishing returns beyond 2x spend; track CAC closely.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 8. Discount / offer / festival ---
    elif _match(q, ["discount", "offer", "deal", "festival", "sale", "coupon", "combo"]):
        answer = (
            f"**Explanation** — Discounts act as a price cut that also attracts deal-seekers. Your margin of "
            f"{margin}% {'allows' if margin > 10 else 'limits'} room for offers.\n\n"
            f"**Prediction** — A 10–15% discount typically boosts volume 20–30% for 1–2 weeks. Festival periods "
            f"amplify this by 1.5–2×. Net profit impact depends on margin buffer.\n\n"
            f"**Recommendation** — {'Launch a 10–15% festival offer on top-selling products with marketing push. Use the Simulator festival-offer preset to model it.' if margin > 10 else 'Your margin is too thin for broad discounts. Try buy-2-get-1 bundles on high-margin items only.'}\n\n"
            f"**Risk** — Customers may delay purchases waiting for the next offer.\n\n**Confidence:** Medium-High"
        )
        confidence = "Medium"

    # --- 9. Cost / expense reduction ---
    elif _match(q, ["cost", "expense", "spend", "save", "cut cost", "reduce cost", "overhead", "opex"]):
        answer = (
            f"**Explanation** — Monthly expenses are {fmt(exp)} ({exp_chg:+.1f}% vs last month). "
            f"COGS is typically ~55% of this ({fmt(exp * 0.55)}), payroll ~20%, and overheads ~25%.\n\n"
            f"**Prediction** — A 10% reduction in operating expenses would add ~{fmt(exp * 0.10)} to monthly "
            f"profit, lifting margin from {margin}% to ~{margin + 10 * exp / max(rev, 1) * 100 / 100:.1f}%.\n\n"
            f"**Recommendation** — Start with supplier renegotiation (biggest lever), then review energy costs "
            f"and staffing efficiency. Run the 'Cut OpEx 15%' scenario in the Simulator.\n\n"
            f"**Risk** — Excessive cost-cutting can hurt service quality and employee morale.\n\n**Confidence:** High"
        )
        confidence = "High"

    # --- 10. Customer growth / retention ---
    elif _match(q, ["customer", "footfall", "visitor", "retain", "loyalty", "churn", "grow customer", "attract"]):
        retention_est = max(100 - kpis.get("customer_change_pct", 0), 70)
        answer = (
            f"**Explanation** — You served {customers:,} customers this month ({cust_chg:+.1f}% change). "
            f"Customer health pillar is at {pillars.get('customers', 50)}/100.\n\n"
            f"**Prediction** — {'Customer count is growing — focus on retention to compound gains.' if cust_chg > 0 else 'Footfall is declining — without intervention, expect further 3–5% drop next month.'}\n\n"
            f"**Recommendation** — {'Launch a loyalty program (stamp cards work well for your segment) and maintain current marketing.' if cust_chg >= 0 else 'Boost marketing 25–40% for 3 weeks, introduce a referral discount, and check if stockouts are driving customers away.'}\n\n"
            f"**Risk** — Acquiring new customers costs 5–7× more than retaining existing ones.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 11. Revenue growth ---
    elif _match(q, ["revenue", "income", "turnover", "sales grow", "increase sales", "grow", "scale", "expand"]):
        answer = (
            f"**Explanation** — Monthly revenue is {fmt(rev)} ({rev_chg:+.1f}% change). Your three main growth "
            f"levers are: (1) increase footfall via marketing, (2) raise average ticket via upselling/bundles, "
            f"(3) extend operating hours.\n\n"
            f"**Prediction** — Combining a 25% marketing boost with 2-hour evening extension could lift revenue "
            f"~8–12% ({fmt(rev * 0.10)}/month) based on your twin's elasticity model.\n\n"
            f"**Recommendation** — Run the 'Extend hours' and 'Double marketing' presets in the Simulator side "
            f"by side, then combine the best levers into a custom scenario.\n\n"
            f"**Risk** — Growth without margin improvement just increases expenses proportionally.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 12. Forecast / future / predict ---
    elif _match(q, ["forecast", "predict", "future", "next month", "next week", "trend", "projection"]):
        trend_dir = "upward" if rev_chg > 0 else "downward" if rev_chg < -2 else "flat"
        answer = (
            f"**Explanation** — Based on 180 days of twin history, your revenue trend is **{trend_dir}** "
            f"({rev_chg:+.1f}% last month). The forecasting model uses ridge regression with weekly seasonality.\n\n"
            f"**Prediction** — Visit the **Forecasting** page for detailed 30/60/90-day projections with "
            f"confidence bands. Current trajectory suggests next month's revenue around "
            f"{fmt(rev * (1 + rev_chg / 100))}.\n\n"
            f"**Recommendation** — Check the Forecasting page for revenue, customer, and expense projections. "
            f"Use the Simulator to test 'what-if' actions that change the trajectory.\n\n"
            f"**Risk** — Forecasts assume current conditions; external shocks (festivals, competition) can shift outcomes.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 13. Competitor / competition ---
    elif _match(q, ["competitor", "competition", "compete", "rival", "market share"]):
        answer = (
            f"**Explanation** — While I don't track competitor data directly, your twin reveals competitive "
            f"posture through customer trends ({cust_chg:+.1f}%) and margin health ({margin}%). "
            f"{'Stable/growing customers suggest you are holding share.' if cust_chg >= 0 else 'Declining footfall may signal competitive pressure.'}\n\n"
            f"**Prediction** — {'Maintaining current trajectory, you are in a strong position.' if cust_chg >= 0 and margin > 10 else 'Without action, competitive pressure may erode share further.'}\n\n"
            f"**Recommendation** — Differentiate on service quality (your operations score is "
            f"{pillars.get('operations', 50)}/100), loyalty programs, and curated product mix rather than pure "
            f"price wars. Review your twin's Recommendations page for prioritized actions.\n\n"
            f"**Risk** — Price wars erode margins for everyone; compete on value instead.\n\n**Confidence:** Low"
        )
        confidence = "Low"

    # --- 14. Hours / timing ---
    elif _match(q, ["hour", "timing", "open", "close", "weekend", "evening", "shift", "schedule"]):
        working = biz.get("working_hours", "9:00-21:00")
        answer = (
            f"**Explanation** — You currently operate {working}. The twin's peak-hours analysis shows strongest "
            f"marginal demand in late evenings and weekends. Each extra hour captures ~2.5% incremental demand.\n\n"
            f"**Prediction** — Extending by 2 hours on weekends would add ~{fmt(rev * 0.04)}/month in revenue "
            f"with minimal fixed cost increase (~₹{int(exp * 0.015 * 2):,} for utilities/staffing).\n\n"
            f"**Recommendation** — {'Start with 2 extra weekend evening hours as a 4-week pilot. Track footfall per hour to validate.' if profit > 20000 else 'Fix profitability first before extending hours — additional hours add costs.'}\n\n"
            f"**Risk** — Employee fatigue and overtime costs if not managed.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 15. Loan / investment / capital ---
    elif _match(q, ["loan", "invest", "capital", "fund", "borrow", "bank", "finance", "budget"]):
        annual_profit = profit * 12
        answer = (
            f"**Explanation** — Your business generates {fmt(profit)}/month in profit ({fmt(annual_profit)}/year). "
            f"Health score is {overall_health}/100. Lenders typically look at consistent profitability, "
            f"margin trends, and cash flow stability.\n\n"
            f"**Prediction** — {'With positive cash flow and decent margins, you are in a reasonable position for a business loan.' if profit > 30000 and margin > 8 else 'Current profitability may make loan servicing challenging. Improve margins first.'}\n\n"
            f"**Recommendation** — {'If expanding, target a loan ≤ 3× annual profit with EMI < 30% of monthly profit. Use the Simulator to project ROI of the investment.' if profit > 30000 else 'Focus on reaching ₹50K+ monthly profit before taking on debt. Use the Recommendations page for margin-improvement actions.'}\n\n"
            f"**Risk** — Over-leveraging during uncertain demand cycles.\n\n**Confidence:** Medium"
        )
        confidence = "Medium"

    # --- 16. Product mix / which products ---
    elif _match(q, ["product", "which product", "best sell", "top sell", "what sell", "catalog", "range", "sku"]):
        answer = (
            f"**Explanation** — Your inventory is valued at {fmt(inv_value)}. The Inventory Intelligence page "
            f"tracks per-product velocity, margin, and stock health. Fast movers with high margins are your "
            f"star products.\n\n"
            f"**Prediction** — Rebalancing stock toward top-5 sellers and cutting slow movers typically lifts "
            f"revenue 3–5% and frees working capital.\n\n"
            f"**Recommendation** — Open the **Inventory** page → sort by velocity. Restock items marked "
            f"*critical*, clearance items with >60 days of stock, and double down on your highest-margin fast movers.\n\n"
            f"**Risk** — Over-reliance on few SKUs makes you vulnerable to supply disruptions.\n\n**Confidence:** High"
        )
        confidence = "High"

    # --- 17. Supplier ---
    elif _match(q, ["supplier", "vendor", "sourcing", "procurement", "supply chain", "cogs"]):
        answer = (
            f"**Explanation** — COGS accounts for ~55% of your expenses (~{fmt(exp * 0.55)}/month). "
            f"Your supplier panel is visible in the Digital Twin view with reliability and cost index scores.\n\n"
            f"**Prediction** — Switching to a supplier with an 8% lower cost index saves ~{fmt(exp * 0.55 * 0.08)}/month, "
            f"flowing directly to profit.\n\n"
            f"**Recommendation** — Run the 'Cheaper supplier' scenario in the Simulator to quantify the impact. "
            f"Negotiate with your current top-3 suppliers first — a 5% discount is often achievable.\n\n"
            f"**Risk** — Cheaper suppliers may have longer lead times or lower reliability.\n\n**Confidence:** Medium-High"
        )
        confidence = "Medium"

    # --- Dynamic catch-all: pick the most relevant advice based on twin state ---
    else:
        answer = _dynamic_catchall(ctx, kpis, risks, health, pillars, rev, profit, margin,
                                   rev_chg, exp, customers, cust_chg, inv_value, overall_health,
                                   top_risk, top_rec, fmt)
        confidence = "High"

    return {"answer": answer, "source": "twin-engine", "confidence": confidence}


def _dynamic_catchall(ctx, kpis, risks, health, pillars, rev, profit, margin,
                      rev_chg, exp, customers, cust_chg, inv_value, overall_health,
                      top_risk, top_rec, fmt) -> str:
    """Analyze the twin state and produce the most relevant advice instead of
    always returning the same generic snapshot."""

    # Find the weakest health pillar
    weakest_pillar = None
    weakest_score = 100
    for name, score in pillars.items():
        if score < weakest_score:
            weakest_score = score
            weakest_pillar = name

    # Pick advice based on the most urgent issue
    if profit < 0:
        return (
            f"**Analysis** — Your business is running at a **loss**: expenses ({fmt(exp)}) exceed revenue "
            f"({fmt(rev)}) by {fmt(-profit)}/month. This is the most urgent issue to address.\n\n"
            f"**Prediction** — Without intervention, cash reserves will deplete within a few months.\n\n"
            f"**Recommendation** — Immediately: (1) renegotiate top supplier contracts for 5–10% savings, "
            f"(2) cut non-essential operating expenses, (3) run a clearance offer to convert dead stock into "
            f"cash. Use the Simulator to model 'Cut OpEx 15%' + 'Cheaper supplier' combined.\n\n"
            f"**Risk** — {top_risk}\n\n**Confidence:** High (grounded in your live twin data)"
        )

    if margin < 5:
        return (
            f"**Analysis** — Your profit margin is critically low at **{margin}%** — one bad month from losses. "
            f"Monthly profit is only {fmt(profit)} on {fmt(rev)} revenue.\n\n"
            f"**Prediction** — Any demand dip or cost increase could push you into negative territory.\n\n"
            f"**Recommendation** — Priority actions: (1) {top_rec}, (2) Review your expense breakdown in "
            f"Financials — COGS is likely your biggest lever. Ask me *\"How can I reduce costs?\"* or "
            f"*\"Should I raise prices?\"* for specific strategies.\n\n"
            f"**Risk** — {top_risk}\n\n**Confidence:** High (grounded in your live twin data)"
        )

    if rev_chg < -5:
        return (
            f"**Analysis** — Revenue is **declining** at {rev_chg:+.1f}% month-over-month. Current monthly "
            f"revenue is {fmt(rev)} with {customers:,} customers ({cust_chg:+.1f}% change).\n\n"
            f"**Prediction** — If this trend continues, expect ~{fmt(rev * (1 + rev_chg / 100))} next month.\n\n"
            f"**Recommendation** — {top_rec}. Check Inventory Intelligence for stockouts and run the "
            f"'Boost marketing' scenario. Ask me *\"Why did sales decrease?\"* or *\"How can I grow revenue?\"* "
            f"for deeper analysis.\n\n"
            f"**Risk** — {top_risk}\n\n**Confidence:** High (grounded in your live twin data)"
        )

    if weakest_pillar and weakest_score < 45:
        pillar_advice = {
            "finance": f"Your finance health is only {weakest_score}/100. Focus on improving margins — ask me *\"How can I improve profit margin?\"*",
            "inventory": f"Inventory health is {weakest_score}/100 — likely stockouts or overstock. Ask me *\"Which products should I stock more?\"*",
            "operations": f"Operations score is {weakest_score}/100 — team may be overstretched. Ask me *\"Should I hire another employee?\"*",
            "customers": f"Customer health is {weakest_score}/100 — footfall may be dropping. Ask me *\"How can I grow customers?\"*",
            "marketing": f"Marketing health is {weakest_score}/100 — not enough new customers. Ask me *\"How should I market my business?\"*",
        }
        return (
            f"**Analysis** — Overall health is {overall_health}/100. Your weakest area is **{weakest_pillar}** "
            f"at {weakest_score}/100. Revenue: {fmt(rev)}/mo ({rev_chg:+.1f}%), profit: {fmt(profit)} ({margin}% margin).\n\n"
            f"**Prediction** — Improving your weakest pillar offers the biggest bang for effort.\n\n"
            f"**Recommendation** — {pillar_advice.get(weakest_pillar, top_rec)}. "
            f"Also: {top_rec}\n\n"
            f"**Risk** — {top_risk}\n\n**Confidence:** High (grounded in your live twin data)"
        )

    # Business is generally healthy — give a growth-oriented overview
    return (
        f"**Business snapshot** — Revenue {fmt(rev)}/mo ({rev_chg:+.1f}%), profit {fmt(profit)} "
        f"({margin}% margin), health score {overall_health}/100.\n\n"
        f"**Top risk** — {top_risk}\n\n"
        f"**Recommendation** — {top_rec}\n\n"
        f"Try asking me specific questions like:\n"
        f"• *\"Should I hire another employee?\"*\n"
        f"• *\"What happens if I increase price by 10%?\"*\n"
        f"• *\"How can I improve my profit margin?\"*\n"
        f"• *\"Should I launch a discount offer?\"*\n"
        f"• *\"How should I market my business?\"*\n"
        f"• *\"What's my revenue forecast for next month?\"*\n\n"
        f"**Confidence:** High (grounded in your live twin data)"
    )


def _match(q: str, primary: list[str], secondary: list[str] | None = None) -> bool:
    """Check if the question matches any primary keyword, optionally with a secondary keyword."""
    has_primary = any(kw in q for kw in primary)
    if not has_primary:
        return False
    if secondary is None:
        return True
    return any(kw in q for kw in secondary)
