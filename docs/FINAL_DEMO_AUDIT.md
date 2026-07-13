# TwinBiz AI — Final Demo Audit (Milestone 1)

Audited: 2026-07-09. Repo state: 4 commits, clean tree, branch `main`.

> **STATUS UPDATE (2026-07-09, end of session): all 22 milestones implemented.**
> Landing-page pricing removed · /products CRUD · /data-center CSV/XLSX import ·
> product-level price simulation + named presets + transparency panels · twin status
> (LIVE/DEMO/STALE, data quality, confidence) · full Product Launch Lab (/product-lab:
> price/discount/inventory sweeps, optimizer, risk score, cannibalization, break-even,
> before/after, launch verdict, Amul Protein Lassi demo preset) · customer segments +
> behaviour predictions · grounded advisor context · setup start modes (demo/upload/manual) ·
> 17 pytest engine tests (`backend/tests/`) + 26-check API smoke test
> (`backend/scripts/smoke_test.py`) — all green · frontend production build passes.
> The sections below are the pre-implementation audit, kept for reference.

---

## 1. Current architecture

```
frontend/  Next.js 16 App Router + TS + Tailwind v4 + Framer Motion + Recharts + Lucide
  src/app/           17 routes (landing, login, register, setup, dashboard, twin, simulator,
                     scenarios, forecast, advisor, inventory, finance, customers, risks,
                     recommendations, alerts, reports, settings)
  src/components/    shell.tsx (sidebar/nav), ui.tsx, charts.tsx
  src/lib/api.ts     fetch wrapper, JWT in localStorage, auto local/deployed base URL

backend/   FastAPI + SQLAlchemy 2 + SQLite (Postgres-ready) + numpy/sklearn
  app/models.py      User, Business, Product, Employee, Supplier, DailyMetric,
                     ProductSale, Scenario, ChatMessage
  app/routers/       auth, business (+twin snapshot, product CRUD), analytics
                     (dashboard/finance/customers), simulate (run/what-if/scenarios/
                     forecast/restock), insights_router (risks/recs/alerts/health/
                     advisor/report/csv)
  app/services/      simulation.py (elasticity engine), forecasting.py (Ridge +
                     weekday seasonality), insights.py (risks/recs/health/alerts),
                     gemini.py (Gemini + offline fallback)
  app/seed.py        365-day synthetic history generator
```

Twin granularity today: **business-level** (`DailyMetric` daily aggregates + `ProductSale`
per-product daily units for the last 120 days). Simulation operates on whole-business levers.

## 2. Working features (verified by code inspection)

- Auth: register/login, PBKDF2 hashing, JWT (7-day), demo account auto-seed
  (demo@twinbiz.ai / demo1234 → "FreshMart Supermarket").
- Business setup (`/setup`) → creates business → seeds 365-day history.
- Dashboard: KPIs, health score (5 pillars), 90-day trend, weekly aggregation,
  top products, peak hours.
- Digital Twin page: product/employee/supplier snapshot with per-product status.
- Simulator: 8 levers, elasticity-based engine (price elasticity by business type,
  tanh diminishing-returns marketing, staffing capacity, satisfaction/churn/health/risk).
  Deterministic — **no random numbers** in simulation. Good foundation.
- What-if presets: 10 presets ranked by profit delta.
- Scenarios: save/list/delete + best-scenario highlight.
- Forecasting: Ridge regression + weekday one-hot, confidence band (1.28σ), R² confidence.
- Inventory: restock predictions (days-until-stockout, suggested order).
- Risks / Recommendations / Alerts / Health: rule-based, computed from real DailyMetrics.
- AI Advisor: Gemini (when key set) grounded in twin context; extensive deterministic
  offline fallback (17 intent branches).
- Reports: JSON + CSV export (daily/weekly/monthly).
- Docker + docker-compose; SQLite default, Postgres supported.

## 3. Broken / weak spots

- No product-level simulation: "increase MILK price by ₹2" (the headline demo!) is not
  possible — only business-wide % price change.
- `business.py create_business` **always** seeds 365 days of synthetic data — a real
  business cannot start empty; synthetic data silently masquerades as real. Violates
  "clearly label demo data".
- No twin status (LIVE/DEMO/STALE), no data-quality/confidence indicators anywhere.
- Products CRUD API exists but there is **no /products page** in the frontend.
- Elasticity is a fixed per-business-type constant; never estimated from history.
- `peak_hours` on dashboard is a hardcoded weight curve (deterministic, but presented
  as data — must be labeled as an estimated profile).
- Finance expense breakdown uses fixed shares (55% COGS etc.) — estimate, unlabeled.

## 4. Demo-only features

- seed.py: entire 365-day history, employees, suppliers, product catalog are synthetic
  (random with per-business fixed seed → reproducible but fake).
- Landing page testimonials are fictional.
- Advisor fallback percentage claims ("5% increase drops demand 7–9%") are canned, not
  computed from the engine.

## 5. Hardcoded values

- `simulation.py`: avg_salary 18000, cogs_share 0.55, marketing = 5% of expenses.
- `analytics.py`: peak-hour weights, expense breakdown shares, CLV 12-month horizon.
- `api.ts`: deployed API base `https://twinbiz-ai.onrender.com` hardcoded fallback.
- `config.py`: dev JWT secret default (acceptable for demo; .env overrides).

## 6. Random / fake prediction logic

- **None in the simulation path** (good). Randomness is confined to seed.py data
  generation (seeded RNG). Forecast/simulation/risks are deterministic.

## 7. Payment / pricing surfaces to remove

- `frontend/src/app/page.tsx`: `#pricing` nav link, "Simple pricing" section, `PLANS`
  array, and one testimonial mentioning "subscription". **No other payment code exists**
  (no Stripe/Razorpay/billing anywhere). App sidebar is already clean.

## 8. Missing problem-statement requirements

| Requirement (§) | Status |
|---|---|
| /products management page (§6) | missing (API partial) |
| /data-center CSV/XLSX import (§7) | missing entirely |
| Product-level price simulation (§11) | missing |
| Named presets "Milk +₹2", "Hire 1 cashier" (§13) | partially (business-level only) |
| Product Launch Lab (§15–34) | missing entirely — biggest gap |
| Price sweep min→max with recommendations (§17–18) | missing |
| Discount/Inventory/Supplier/Marketing labs (§19–22) | missing |
| Launch timing, segments, shelf placement, competitor, cannibalization (§23–28) | missing |
| Break-even, launch risk score, launch optimizer (§29–33) | missing |
| Twin status LIVE/DEMO/STALE + data quality + confidence (§9–10) | missing |
| "How was this predicted?" transparency (§47) | missing |
| Customer segments & behaviour prediction (§24) | partial (aggregates only) |
| Advisor grounding with simulations/experiments (§40–41) | partial |
| Demo presets "Load SmartMart" / "Launch New Product Demo" (§49) | partial (demo account only) |

## 9. Reusable code

- `simulation.py` elasticity engine → extend for product-level + experiment engine.
- `forecasting.py` → reuse for demand forecasts in launch lab (category history).
- `insights.py` risk/rec pattern → extend with confidence fields.
- `Scenario` model pattern (levers_json/results_json) → reuse for experiment scenarios.
- `seed.py` catalog → upgrade to branded SmartMart catalog with SKUs.
- shell/ui/charts components → all new pages reuse them.

## 10. Files to modify

- `frontend/src/app/page.tsx` — remove pricing section/nav/PLANS.
- `frontend/src/components/shell.tsx` — add Products, Product Lab, Data Center nav.
- `backend/app/models.py` — extend Product; add data_source to Business; add
  ProductExperiment/…Scenario/…Result.
- `backend/app/routers/business.py` — products CRUD moves richer; seed becomes opt-in.
- `backend/app/main.py` — register new routers; additive SQLite column migration.
- `backend/app/routers/simulate.py` — product-level price simulation + assumptions.
- `backend/app/services/gemini.py` / `insights_router.py` — extended advisor context,
  launch advisor.
- `frontend/src/app/setup/page.tsx` — "How do you want to start?" (demo vs empty).
- `frontend/src/app/twin/page.tsx` — twin status header.
- `frontend/src/app/simulator/page.tsx` — presets + product price mode + transparency.

## 11. Files to create

- `backend/app/routers/products.py` — full product CRUD w/ search/sort/pagination.
- `backend/app/routers/data_center.py` — CSV/XLSX preview/map/validate/import.
- `backend/app/routers/experiments.py` — product-experiment API (§45).
- `backend/app/services/launch_lab.py` — experiment engine: landed cost, price sweep,
  discount sweep, inventory sweep, marketing curve, cannibalization, break-even,
  risk score, confidence, constrained grid-search optimizer.
- `backend/app/services/import_engine.py` — column auto-mapping + validation.
- `backend/tests/test_simulation.py`, `test_launch_lab.py`.
- `frontend/src/app/products/page.tsx`
- `frontend/src/app/data-center/page.tsx`
- `frontend/src/app/product-lab/page.tsx`
- `docs/FINAL_DEMO_AUDIT.md` (this file).

## 12. Database changes (SQLite-safe: additive columns + new tables only)

- `businesses`: + `data_source` ("demo" | "real" | "mixed"), + `avg_daily_customers?`
  (already covered by customer_count), + `suppliers_count` not needed (relation exists).
- `products`: + sku, brand, unit_type, unit_size, subcategory, mrp, tax_rate,
  min_stock, max_stock, safety_stock, reorder_qty, supplier_id, lead_time_days,
  shelf_life_days (rename semantics of expiry_days kept), storage_type, shelf_location,
  is_demo flag. All nullable/defaulted → `ALTER TABLE ADD COLUMN` on startup.
- New tables: `product_experiments`, `product_experiment_scenarios`,
  `product_experiment_results` (per §44).

## 13. Recommended implementation order (matches master-prompt milestones)

1. ✅ This audit.
2. Verify runnable baseline (backend boots, frontend builds).
3. Remove landing-page pricing (only payment surface found).
4. Products module (model + API + page).
5. Data Center import.
6. Simulator upgrades: product-level price sim, named presets, transparency block,
   twin status chips.
7. **Product Launch Lab** (engine → API → UI → optimizer → demo preset). Largest item;
   the judge-winning feature.
8. Customers segments, advisor grounding (+"Should I launch?").
9. Demo presets, tests, final polish.

## 14. Highest-priority first coding task

Remove pricing section (5 min), then start Products module — Launch Lab depends on the
richer product/cost fields it introduces.
