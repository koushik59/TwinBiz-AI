"""End-to-end API smoke test against a running backend (26 checks).

Usage:
    1. Start the backend:  .venv/Scripts/python -m uvicorn app.main:app --port 8000
    2. Run:                .venv/Scripts/python scripts/smoke_test.py

Logs in as the auto-seeded demo account and exercises every major endpoint,
including the full Product Launch Lab flow. Exits non-zero on any failure.
Note: creates a demo scenario + experiment — delete backend/twinbiz.db afterwards
for a pristine demo database (it reseeds on next startup).
"""

import json
import sys
import urllib.request

BASE = "http://localhost:8000"


def login() -> str:
    req = urllib.request.Request(
        BASE + "/api/auth/login", method="POST",
        data=json.dumps({"email": "demo@twinbiz.ai", "password": "demo1234"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def main() -> int:
    token = login()

    def call(method, path, body=None):
        req = urllib.request.Request(
            BASE + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))
        print(("PASS" if cond else "FAIL"), name)

    d = call("GET", "/api/analytics/dashboard")
    check("dashboard kpis + twin_status", d["kpis"]["monthly_revenue"] > 0 and d["twin_status"]["status"] in ("DEMO", "LIVE"))
    check("health pillars", len(d["health"]["pillars"]) == 5)

    t = call("GET", "/api/business/twin")
    check("twin has branded products", len(t["products"]) >= 20)
    check("twin status block", "data_source" in t["twin_status"])

    p = call("GET", "/api/products?search=amul&page_size=50")
    check("products search", p["total"] >= 4)

    milk = next(i for i in call("GET", "/api/simulate/products")["items"] if "Milk" in i["name"])
    pp = call("POST", "/api/simulate/product-price", {"product_id": milk["id"], "new_price": milk["price"] + 2})
    check("milk +2 price sim: demand falls, profit rises",
          pp["delta"]["demand_pct"] < 0 < pp["delta"]["gross_profit"] and pp["assumptions"])

    w = call("GET", "/api/simulate/what-if")
    keys = [a["key"] for a in w["actions"]]
    check("what-if includes milk presets", "milk_price_up_2" in keys and "hire_1_cashier" in keys)

    r = call("POST", "/api/simulate/run", {"price_change_pct": 5})
    check("simulate run has transparency", "assumptions" in r["how"])

    call("POST", "/api/simulate/scenarios", {"name": "Smoke scenario", "levers": {"price_change_pct": 5}})
    ls = call("GET", "/api/simulate/scenarios")
    check("scenario highlights", "highlights" in ls and ls["highlights"]["ai_recommended"])

    f = call("GET", "/api/simulate/forecast?metric=revenue&horizon=30")
    check("forecast 30d + confidence", len(f["forecast"]) == 30 and f["confidence"] > 0)

    preset = call("GET", "/api/product-experiments/demo-preset")
    exp = call("POST", "/api/product-experiments", preset)
    check("experiment created", exp["landed_cost"] > 25)

    sweep = call("POST", f"/api/product-experiments/{exp['id']}/price-sweep")
    check("price sweep 11 points", len(sweep["points"]) == 11)
    check("best profit not max price", sweep["recommendations"]["best_profit"]["price"] < preset["max_price"])

    disc = call("POST", f"/api/product-experiments/{exp['id']}/discount-sweep", {})
    check("discount sweep", len(disc["points"]) == 5)

    inv = call("POST", f"/api/product-experiments/{exp['id']}/inventory-sweep", {})
    check("inventory recommends stock", inv["recommended_stock"] > 0)

    opt = call("POST", f"/api/product-experiments/{exp['id']}/optimize", {"min_margin_pct": 10})
    check("optimizer 4 strategies", len(opt["strategies"]) == 4)

    ana = call("POST", f"/api/product-experiments/{exp['id']}/analysis")
    check("analysis cannibalization finds lassi",
          any("Lassi" in v["product"] for v in ana["cannibalization"]["affected_products"]))
    check("before/after present", ana["before_after"]["with"]["revenue"] > ana["before_after"]["without"]["revenue"])

    verdict = call("POST", f"/api/product-experiments/{exp['id']}/advisor")
    check("launch verdict", verdict["decision"] in {"YES", "CONDITIONAL YES", "WAIT", "HIGH RISK"})

    lab_sc = call("POST", f"/api/product-experiments/{exp['id']}/scenarios",
                  {"name": "Premium Launch", "price": 44, "discount": 0, "stock": 300, "marketing_budget": 2500})
    comp = call("GET", f"/api/product-experiments/{exp['id']}/scenarios")
    check("lab scenario comparison", lab_sc["id"] in [i["id"] for i in comp["items"]])

    cust = call("GET", "/api/analytics/customers")
    check("customer segments labeled",
          len(cust["segments"]) == 5 and "aggregate" in cust["predictions"]["label"].lower())

    recs = call("GET", "/api/insights/recommendations")["recommendations"]
    check("recs have confidence", all("confidence_pct" in x for x in recs))

    adv = call("POST", "/api/insights/advisor", {"message": "What happens if I increase milk price by 2 rupees?"})
    check("advisor answers", len(adv["answer"]) > 50)

    check("alerts endpoint", "alerts" in call("GET", "/api/insights/alerts"))

    dc = call("GET", "/api/data-center/status")
    check("data center status", dc["counts"]["products"] >= 20)

    types = call("GET", "/api/data-center/types")
    check("import types", set(types["types"]) == {"products", "sales", "daily_metrics",
                                                  "expenses", "suppliers", "employees"})

    fails = [n for n, ok in checks if not ok]
    print(f"\n{len(checks) - len(fails)}/{len(checks)} passed"
          + (f" — FAILURES: {fails}" if fails else " — ALL GREEN"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
