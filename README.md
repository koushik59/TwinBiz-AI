# TwinBiz AI — Predict Before You Decide 🔮

**An AI-Powered Digital Twin Platform for Small & Medium Enterprises.**

TwinBiz AI creates a living virtual replica (*digital twin*) of a business where owners can
**simulate decisions before implementing them in real life** — test a price change, a new hire,
a festival offer or an inventory move, and see the predicted impact on revenue, profit,
customers and risk *before spending real money*.

> Theme: **Analytics & Decision Intelligence**

---

## ✨ Features

| Module | What it does |
|---|---|
| **Product Launch Lab** 🚀 | *Test before you stock*: define a virtual new product (costs, price range, stock, marketing, segment, shelf placement, competitor price) → price sweep ₹min→₹max, discount lab, inventory lab, cannibalization estimate, break-even, 0–100 launch risk score, deterministic grid-search **“Find Best Launch Strategy”**, and a *“Should I launch this product?”* verdict |
| **AI Business Simulator** | 8 business levers **plus product-level price simulation** (“What if I raise Amul Milk by ₹2?” → demand, revenue, gross profit, satisfaction, substitution risk — with elasticity assumptions and confidence shown) |
| **What-If Analysis** | One-click presets: milk price ±₹2, hire one extra cashier, 10% festival offer, marketing +20%… ranked by profit impact |
| **Products** | Full catalog management: SKUs, brands, pricing/MRP/tax, stock levels, supplier terms, shelf life — search, filter, sort, pagination |
| **Data Center** | CSV/XLSX import of real business data (products, sales, daily totals, expenses, suppliers, employees) with auto column-mapping, per-row validation and a demo-vs-real data source badge |
| **Scenario Comparison** | Save strategies, compare Current vs A/B/C side-by-side, best scenario auto-highlighted |
| **ML Forecasting** | Ridge regression + weekly seasonality on 365 days of history: sales, demand, customers, expenses with confidence bands |
| **AI Business Advisor** | Chat grounded in live twin data — Gemini API when a key is set, built-in Twin Engine fallback offline |
| **Digital Twin View** | Interactive store layout: click any shelf, employee or supplier for live metrics + AI advice |
| **Inventory Intelligence** | Days-to-stockout, restock-by dates, suggested order quantities, fast/slow movers |
| **Risk Analyzer** | Stockouts, overstock, negative cash flow, declining sales, churn, understaffing — severity ranked |
| **Recommendation Engine** | Prioritized actions with reason, expected benefit and estimated ₹ uplift |
| **Financial Analytics** | 12-month P&L, expense breakdown, cumulative cash flow, ROI, break-even |
| **Business Health Score** | 0–100 across finance, inventory, operations, customers, marketing with animated gauges |
| **Alert Center & Reports** | Color-coded alerts; daily/weekly/monthly reports with CSV export and print-to-PDF |

Plus: JWT auth, setup wizard with **Demo / Upload / Manual start modes**, clearly-labeled
365-day demo dataset (weekly seasonality, Indian festival spikes, growth trend), twin status
header (LIVE / DEMO / STALE + data quality + confidence), a "How was this predicted?" panel on
every simulation, customer segments & behaviour predictions (aggregate, labeled), dark/light/auto
theme, glassmorphism UI, Framer-Motion animations, fully responsive.

**Every prediction is deterministic and explainable — no random numbers, and demo data is never
passed off as real.** Engine tests: `cd backend && .venv/Scripts/python -m pytest tests/` ·
full API smoke test (26 checks): `.venv/Scripts/python scripts/smoke_test.py`.

## 🏗 Tech Stack

- **Frontend:** Next.js (App Router) · React · TypeScript · Tailwind CSS v4 · Framer Motion · Recharts · Lucide
- **Backend:** FastAPI · Python · SQLAlchemy 2 · scikit-learn · NumPy · Pandas
- **Database:** SQLite for instant local demo, PostgreSQL in Docker/production (same code, one env var)
- **AI:** Google Gemini API (with offline rule-engine fallback grounded in twin data)
- **Auth:** JWT (PBKDF2-hashed passwords)
- **Deploy:** Docker + docker-compose

## 🚀 Quick Start (local, no Docker)

**Backend** (Python 3.12+):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --reload
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

**Demo login (auto-seeded):** `demo@twinbiz.ai` / `demo1234` — a supermarket twin with a full
year of data, or register and create your own twin in the setup wizard.

API docs: http://localhost:8000/docs

## 🐳 Docker (with PostgreSQL)

```bash
GEMINI_API_KEY=your-key docker compose up --build
```

Frontend on :3000, API on :8000, Postgres persisted in a volume.

## 🔑 Environment

`backend/.env` (see `.env.example`):

```
DATABASE_URL=sqlite:///./twinbiz.db     # or postgresql://user:pass@host:5432/twinbiz
JWT_SECRET=change-me
GEMINI_API_KEY=                         # optional — advisor falls back to Twin Engine
```

`frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000`

## 🧠 How the simulation works

Each business type has calibrated **price elasticity of demand** and **marketing response**
curves. The engine reconstructs a monthly baseline from the twin's actual trailing-30-day
history, then applies lever effects (saturating `tanh` curves for diminishing returns,
stockout throttling, service-capacity effects of staffing) to produce revenue, cost,
satisfaction, churn, cash-flow, health and risk outputs. Forecasts are ridge regressions
over a trend + one-hot weekday design matrix with 80% confidence bands from residual variance.

## 📁 Structure

```
backend/app
├── main.py            # FastAPI app + demo seeding
├── models.py          # SQLAlchemy schema (users, businesses, products, metrics…)
├── seed.py            # 365-day realistic data generator
├── security.py        # JWT + PBKDF2
├── services/
│   ├── simulation.py    # elasticity-based what-if engine (+ product-level pricing)
│   ├── launch_lab.py    # Product Launch Lab engine: sweeps, optimizer, risk, cannibalization
│   ├── forecasting.py   # ML forecasts + restock predictions
│   ├── import_engine.py # CSV/XLSX auto-mapping + validation
│   ├── insights.py      # risks, recommendations, health score, alerts, twin status
│   └── gemini.py        # AI advisor (Gemini + offline fallback)
└── routers/             # auth, business, products, data_center, experiments,
                         # analytics, simulate, insights

frontend/src
├── app/               # 19 routes: landing, auth, setup, dashboard, product-lab, data-center…
├── components/        # design system (ui), charts, app shell
└── lib/               # API client, formatters
```

## 🎬 Suggested demo flow

1. Log in with the demo account → **Dashboard** (twin status, KPIs, risks, AI suggestions)
2. **Digital Twin** → click the Dairy shelf → live per-product metrics
3. **Simulator → Product Price** → Amul Milk ₹28 → ₹30 → demand −6%, gross profit +41%, assumptions & confidence
4. **Product Launch Lab** → *Launch New Product Demo* (Amul Protein Lassi 200ml) → Create
5. Run **Price Sweep** ₹30–₹50 → best-profit / best-adoption / balanced price cards
6. **Discount Lab** and **Inventory Lab** → recommended launch offer + initial stock
7. **Find Best Launch Strategy** → grid-searched recommended strategy
8. **Launch Analysis** → risk score, break-even, cannibalization of Regular Lassi, WITHOUT vs WITH view
9. **“Should I Launch This Product?”** → twin-engine verdict (+ Gemini narration when key set)
10. **AI Advisor**: *“Should I launch this product?” / “What should I do today?”*

---

Built with ❤️ for the Ideathon — *TwinBiz AI: your business, twice. One in the real world, one where mistakes are free.*
