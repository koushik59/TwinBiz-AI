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
| **AI Business Simulator** | 8 decision levers (price, marketing, staffing, discount, inventory, hours, supplier cost, OpEx) → instant elasticity-based predictions of revenue, profit, demand, churn, cash flow, health & risk |
| **What-If Analysis** | One-click presets: raise price, hire staff, festival offer, switch supplier… ranked by profit impact |
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

Plus: JWT auth, guided business-setup wizard, **auto-generated 365-day realistic dataset**
(weekly seasonality, Indian festival spikes, growth trend), dark/light mode, glassmorphism UI,
Framer-Motion animations, fully responsive.

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
│   ├── simulation.py  # elasticity-based what-if engine
│   ├── forecasting.py # ML forecasts + restock predictions
│   ├── insights.py    # risks, recommendations, health score, alerts
│   └── gemini.py      # AI advisor (Gemini + offline fallback)
└── routers/           # auth, business, analytics, simulate, insights

frontend/src
├── app/               # 16 routes: landing, auth, setup, dashboard, simulator…
├── components/        # design system (ui), charts, app shell
└── lib/               # API client, formatters
```

---

Built with ❤️ for the Ideathon — *TwinBiz AI: your business, twice. One in the real world, one where mistakes are free.*
