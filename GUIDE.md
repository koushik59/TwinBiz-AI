# TwinBiz AI — Complete Run & Feature Guide

Everything you need to **start**, **stop**, and **demo** the project, plus a plain-language
explanation of what every feature actually does under the hood.

---

## 1. What is this project?

TwinBiz AI is a full-stack web app with **two servers** that must both be running:

| Part | Tech | Port | URL |
|---|---|---|---|
| **Backend** (the brain: API, database, AI, ML) | FastAPI (Python) | 8000 | http://localhost:8000 |
| **Frontend** (the website you see) | Next.js (React) | 3000 | http://localhost:3000 |

The frontend calls the backend for every piece of data. If the backend is not running,
pages will load but stay stuck on loading skeletons.

---

## 2. How to RUN it

Open **two separate terminals** (PowerShell or CMD, both work).

### Terminal 1 — Backend

```powershell
cd d:\ideathon\backend
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Wait until it says `Uvicorn running on http://127.0.0.1:8000`.

> ⚠️ **Do NOT use `--reload` on this machine.** The reload worker sometimes gets orphaned
> and keeps serving old code on port 8000 even after you stop it. Plain mode is reliable.

> First time on a new machine (venv doesn't exist yet):
> ```powershell
> cd d:\ideathon\backend
> python -m venv .venv
> .venv\Scripts\pip install -r requirements.txt
> ```

### Terminal 2 — Frontend

**For the hackathon demo (fast, polished, recommended):**
```powershell
cd d:\ideathon\frontend
npm run build     # only needed once, or after you change frontend code
npm start
```

**For development (hot reload while editing code):**
```powershell
cd d:\ideathon\frontend
npm run dev
```

### Then open the app

1. Go to **http://localhost:3000**
2. Click **Sign in** — demo credentials are pre-filled:
   - Email: `demo@twinbiz.ai`
   - Password: `demo1234`
3. You land on the dashboard of "FreshMart Supermarket" with a full year of data.

Other useful URLs:
- **http://localhost:8000/docs** — interactive API documentation (Swagger). Great to show judges the backend.
- **http://localhost:8000/api/healthz** — quick check that the backend is alive.

---

## 3. How to STOP it

### Normal stop
In each terminal, press **`Ctrl + C`** once. That's it. Then you can close the terminal windows.

### If a terminal was closed without Ctrl+C (server still running in background)

Check what is holding the ports:
```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :3000
```
The last number on each line is the **PID**. Kill it:
```powershell
taskkill /PID <that-number> /F
```

Nuclear option (kills ALL python/node processes — only if nothing else important is running):
```powershell
taskkill /IM python.exe /F
taskkill /IM node.exe /F
```

### Resetting the data
All data lives in your MongoDB Atlas database (`MONGODB_DB`, default `twinbiz`). To start
completely fresh, drop that database from the Atlas UI (Browse Collections → Drop Database)
or point `MONGODB_DB` at a new name — the backend recreates the indexes and demo account
automatically on next startup.

---

## 4. Configuration (`backend/app/config.py` and `.env`)

| Setting | What it does |
|---|---|
| `mongodb_uri` | MongoDB Atlas connection string (SRV). Put it in `backend\.env` as `MONGODB_URI`. |
| `mongodb_db` | Database name inside the cluster (default `twinbiz`). |
| `jwt_secret` | Secret used to sign login tokens. |
| `gemini_api_key` | If set, the AI Advisor uses **real Google Gemini**. If empty, it uses the built-in offline Twin Engine (demo still works perfectly). |
| `cors_origins` | Which frontend URLs are allowed to call the API. |

> 🔒 **Security note:** prefer putting the Gemini key in `backend\.env` as
> `GEMINI_API_KEY=your-key` instead of hardcoding it in `config.py`. The `.env` file is
> git-ignored, so the key won't leak if you push this repo to GitHub. Values in `.env`
> automatically override the defaults in `config.py`.

---

## 5. Every functionality, explained

### 🏠 Landing page (`/`)
Marketing homepage: hero with live-simulation mock, animated statistics counters, feature
cards, how-it-works, pricing, testimonials. "Get Started" → register, "View Live Demo" → login.

### 🔐 Login / Register (`/login`, `/register`)
JWT authentication. Passwords are hashed with PBKDF2 (200,000 iterations) — never stored in
plain text. After login the token is kept in the browser and attached to every API call.
All app pages are protected: no token → redirected to login.

### 🧙 Setup wizard (`/setup`)
3-step form for a new user: business name/type/location → scale (employees, revenue,
expenses, customers, hours) → confirm. On submit the backend **generates the digital twin**:
- **365 days** of daily revenue, expenses, customers and orders — with weekday rhythm
  (weekends busier), Indian **festival spikes** (Diwali, Dussehra, Holi…), a growth trend and
  realistic noise
- A product catalog matched to the business type (supermarket gets milk/rice/oil…, bakery
  gets cakes/croissants…), each with price, cost, stock, demand rate
- Employees with roles/salaries/performance and suppliers with reliability/lead time/cost index

This is why charts and ML predictions work instantly with zero manual data entry.

### 📊 Dashboard (`/dashboard`)
The command center. Shows:
- **KPI tiles**: monthly revenue/profit/expenses/customers with % change vs the previous
  30 days, today's revenue/customers/orders, inventory value
- **Business Health gauge** (0–100) — average of 5 pillar scores (see Health below)
- **Revenue vs Expenses chart** (30/90-day toggle), weekly profit trend, customer footfall
- **Top selling products** (last 30 days, from real per-product sales rows)
- **Peak business hours** profile
- **Upcoming Risks** and **AI Suggestions** widgets (live from the risk/recommendation engines)

### 🧬 Digital Twin (`/twin`)
The interactive virtual replica. The store layout is drawn as **departments with shelves**
(one card per product, color-coded: green=healthy, yellow=low, red=critical, orange=overstock).
Click **any shelf, employee, or supplier** → an inspector panel shows its live metrics
(margin, days-of-stock, stock value, salary, performance, reliability…) plus a tailored AI
tip (e.g. "order 140 units now to cover 30 days"). Also shows the financial overview of the twin.

### 🧪 AI Business Simulator (`/simulator`) — ⭐ the star feature
8 sliders = 8 decision levers: **price, marketing budget, employees, discount, inventory
purchase, store hours, supplier cost, operating expenses**. Every slider move re-runs the
simulation (debounced 220 ms) and animates the results:
- Predicted revenue, profit, expenses, customers (with % vs current)
- Cash flow, customer satisfaction, churn risk, inventory days
- **Current vs Simulated** bar chart, animated health gauge, **risk score 0–100** with a
  plain-English verdict strip ("✅ profitable" / "⚠️ reduces profit")

**How the math works:** each business type has a calibrated **price elasticity of demand**
(supermarket −1.8: raise price 10% → demand falls ~17%; pharmacy −0.6: barely reacts).
Marketing follows a **diminishing-returns curve** (tanh) — doubling spend doesn't double
sales. Hiring increases service capacity → satisfaction → demand. Cutting inventory too
deep triggers **stockout throttling** (lost sales). Everything is computed against your
twin's real trailing-30-day history, not made-up numbers.

**Quick What-Ifs**: one-click presets (increase price 10%, hire 2, festival offer, double
marketing, cheaper supplier…). **Save as Scenario** stores the current slider setup + results.

### ⚖️ Scenario Comparison (`/scenarios`)
Compares **Current Business vs up to 3 saved scenarios** in a table across revenue, profit,
expenses, customers, inventory, satisfaction, risk and health. The best value per row is
highlighted green; the overall **best scenario gets a crown** 👑. Scenario cards show
projected profit and risk/health badges. Delete scenarios with the trash icon.

### 📈 Forecasting (`/forecast`)
Machine-learning predictions for **revenue, customers, orders, expenses** over **14/30/60/90
days**. Shows next-day / next-7-day / next-30-day totals, **model confidence** (R² of the
fit) and monthly trend. The chart draws actual history (solid), the prediction (dashed) and
an **80% confidence band** (shaded).

**The model:** Ridge regression trained on the last 180 days with two feature groups — a
linear time trend + one-hot **weekday seasonality** (so it learns "Sundays are big").
Falls back to pure-NumPy least squares if scikit-learn is unavailable.

### 🤖 AI Advisor (`/advisor`)
Chat interface. Every question is sent with a **live snapshot of your business** (KPIs,
health score, top risks, best recommendation) so answers are grounded in *your* numbers, not
generic advice. Answers include explanation → prediction → recommendation → risk →
**confidence score**, and a badge showing the source:
- **Gemini AI** — when `GEMINI_API_KEY` is set (calls `gemini-2.0-flash` via REST)
- **Twin Engine** — offline fallback with hand-built answer templates filled with your real
  data (also used automatically if the Gemini call fails, so the demo can never break)

Chat history is stored in the database and reloads when you return.

### 📦 Inventory Intelligence (`/inventory`)
- KPI tiles: total inventory value, SKUs tracked, critical stockouts, low-stock count
- **Restock predictions table**: per product — current stock, demand/day, **days until
  stockout** (stock ÷ daily demand), a **restock-by date** (3-day safety buffer) and a
  **suggested order quantity** (30 days of demand minus current stock), sorted by urgency
- **Fast movers** (top 5 by demand) and **slow movers** (capital locked in stagnant stock)

### 💰 Financial Analytics (`/finance`)
- 12-month revenue/expenses/profit line chart + month-by-month table with margins
- **Expense breakdown donut** (COGS, payroll, marketing, rent, other)
- **Cumulative cash flow** over 30 days
- **ROI** on expenses and **break-even revenue** (fixed costs ÷ contribution margin) with an
  above/below indicator

### 👥 Customer Analytics (`/customers`)
New vs returning customer trend (180 days), monthly visits, new customers, **retention &
churn rate**, average ticket size, and **Customer Lifetime Value** (avg ticket × visit
frequency × 12 months) — plus written behaviour insights.

### ⚠️ Risk Analyzer (`/risks`)
Continuously scans the twin and reports risks **ranked by severity** (critical / high /
medium / low), each with concrete numbers:
- **Low inventory** — products under 5 days of demand ("Milk runs out in ~3 days")
- **Overstock** — >60 days of stock, shows the ₹ capital locked
- **Negative cash flow / profit margin below 5% / declining sales** (>7% drop vs previous month)
- **Customer churn** (footfall dropping >6%) · **high expense ratio** (>92% of revenue)
- **Understaffing** (>60 customers per employee per day)

### 💡 Recommendation Center (`/recommendations`)
Turns detected risks into **prioritized actions**, each with: the reason (with your real
numbers), the expected benefit, a priority level, and an **estimated ₹ revenue uplift per
month**. Every card has a "Simulate" button that jumps to the Simulator to test it safely.

### ❤️ Business Health Score (shown on dashboard & reports)
Score out of 100 = average of five pillars, each computed from real data:
- **Finance** — profit margin + revenue trend direction
- **Inventory** — share of products in the healthy stock band (5–45 days of demand)
- **Operations** — revenue per employee vs benchmark
- **Customers** — footfall growth trend
- **Marketing** — new-customer share of total visits

### 🔔 Alert Center (`/alerts`)
All risks reframed as color-coded alert cards **plus per-product low-stock alerts** (stock
below reorder level). Filter by severity. The bell icon in the top bar and the sidebar badge
show the live alert count on every page.

### 📄 Reports (`/reports`)
Daily / weekly / monthly report: summary KPIs, health pillar bars, detected risks and
numbered recommended actions — laid out like a printable document.
- **Export CSV** — downloads the raw day-by-day data (date, revenue, expenses, profit, customers, orders)
- **Print / PDF** — opens the browser print dialog; choose "Save as PDF"

### ⚙️ Settings (`/settings`)
Profile card, **dark/light theme toggle** (persisted in the browser), edit all business
details (recalibrates the simulator baseline), and notes on the Gemini integration.

---

## 6. Demo script suggestion (for judging)

1. **Landing page** — show the tagline and scroll the animations (30 s)
2. **Login** with demo account → **Dashboard** — point at health score, risks widget (1 min)
3. **Simulator** — drag price to +10%, show sales drop/profit change; click "Festival offer"
   preset; save it as a scenario (2 min) ← spend the most time here
4. **Scenarios** — show the comparison table and the crowned winner (30 s)
5. **Forecast** — show confidence band and "the model learned weekends" (30 s)
6. **Advisor** — ask *"Should I hire another employee?"* (30 s)
7. **Digital Twin** — click a red shelf, read the AI restock tip (30 s)
8. Finish on **Reports** → Export CSV to show it's production-ready (15 s)

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| Frontend loads but everything is skeletons | Backend isn't running — start Terminal 1 |
| `Error: only one usage of each socket address` on port 8000 | Old backend still alive → see "How to STOP it" and kill the PID |
| Port 3000 busy | Kill the old node PID, or `npm start -- -p 3001` |
| Backend serves old code after edits | You used `--reload` — kill all python PIDs on 8000 and start without it |
| Want fresh demo data | Drop the `twinbiz` database in MongoDB Atlas, restart the backend |
| Advisor answers say "Twin Engine" instead of Gemini | Set a valid `GEMINI_API_KEY` in `backend\.env` and restart the backend |
| Changed frontend code but nothing changes on :3000 | You're on `npm start` (serves the old build) — rebuild with `npm run build`, or use `npm run dev` |
