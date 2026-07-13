"use client";

import { SERIES } from "@/components/charts";
import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, Gauge, Input, PageSkeleton, Select, Slider, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, num, pct } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, FlaskConical, Info, PackageSearch, RotateCcw, Save, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Levers = {
  price_change_pct: number;
  marketing_change_pct: number;
  employee_delta: number;
  discount_pct: number;
  inventory_change_pct: number;
  hours_delta: number;
  supplier_cost_change_pct: number;
  opex_change_pct: number;
};
type SimResult = {
  revenue: number; expenses: number; profit: number; profit_margin_pct: number;
  customers: number; satisfaction: number; churn_risk_pct: number; cash_flow: number;
  inventory_days: number; health_score: number; risk_score: number;
  deltas: { revenue_pct: number; profit_pct: number; expenses_pct: number; customers_pct: number };
};
type How = { model_version: string; baseline_window: string; assumptions: string[]; label: string };
type RunResponse = { current: SimResult; simulated: SimResult; how: How };

type SimProduct = { id: number; name: string; category: string; price: number; cost: number; stock: number };
type PriceSim = {
  product: string; category: string;
  baseline: { price: number; units_per_day: number; monthly_revenue: number; monthly_gross_profit: number; days_of_stock: number };
  proposed: { price: number; units_per_day: number; monthly_revenue: number; monthly_gross_profit: number; days_of_stock: number };
  delta: { demand_pct: number; revenue: number; revenue_pct: number; gross_profit: number; gross_profit_pct: number; satisfaction_pts: number };
  risk: { substitution_pct: number; stockout: string };
  confidence_pct: number; assumptions: string[]; model_version: string; label: string;
};

const ZERO: Levers = {
  price_change_pct: 0, marketing_change_pct: 0, employee_delta: 0, discount_pct: 0,
  inventory_change_pct: 0, hours_delta: 0, supplier_cost_change_pct: 0, opex_change_pct: 0,
};

const WHAT_IFS: { label: string; levers: Partial<Levers> }[] = [
  { label: "👥 Hire one extra cashier", levers: { employee_delta: 1 } },
  { label: "🎉 10% festival offer", levers: { discount_pct: 10, marketing_change_pct: 40, inventory_change_pct: 15 } },
  { label: "📣 Marketing +20%", levers: { marketing_change_pct: 20 } },
  { label: "📦 Stock up 15%", levers: { inventory_change_pct: 15 } },
  { label: "🕘 Extend hours +2", levers: { hours_delta: 2 } },
  { label: "🚚 Cheaper supplier", levers: { supplier_cost_change_pct: -8 } },
  { label: "✂️ Cut OpEx 10%", levers: { opex_change_pct: -10 } },
  { label: "🏷️ Increase prices 10%", levers: { price_change_pct: 10 } },
];

function HowPanel({ how, confidence }: { how: { assumptions: string[]; model_version: string; label?: string; baseline_window?: string }; confidence?: number }) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="p-4">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between text-left cursor-pointer">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-ink-2">
          <Info size={13} className="text-brand" /> How was this predicted?
        </span>
        <span className="flex items-center gap-2">
          {confidence !== undefined && <Badge tone={confidence >= 70 ? "good" : confidence >= 50 ? "medium" : "high"}>Confidence {confidence}%</Badge>}
          <ChevronDown size={14} className={cn("text-muted transition-transform", open && "rotate-180")} />
        </span>
      </button>
      {open && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="overflow-hidden">
          <ul className="mt-3 space-y-1.5 text-xs leading-relaxed text-ink-2">
            {how.assumptions.map((a, i) => (
              <li key={i} className="flex gap-1.5"><span className="text-brand">•</span>{a}</li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-muted">
            {how.baseline_window ? `Baseline: ${how.baseline_window} · ` : ""}Model {how.model_version} · Every figure is <em>{how.label ?? "Predicted (not guaranteed)"}</em>.
          </p>
        </motion.div>
      )}
    </Card>
  );
}

function ProductPriceMode() {
  const { toast } = useToast();
  const [products, setProducts] = useState<SimProduct[]>([]);
  const [productId, setProductId] = useState<number | null>(null);
  const [newPrice, setNewPrice] = useState("");
  const [sim, setSim] = useState<PriceSim | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<{ items: SimProduct[] }>("/api/simulate/products").then((d) => {
      setProducts(d.items);
      const milk = d.items.find((p) => p.name.toLowerCase().includes("milk")) ?? d.items[0];
      if (milk) {
        setProductId(milk.id);
        setNewPrice(String(milk.price + 2));
      }
    }).catch(() => {});
  }, []);

  const selected = products.find((p) => p.id === productId) ?? null;

  const run = async () => {
    if (!selected || !newPrice || Number(newPrice) <= 0) {
      toast("Pick a product and a valid new price", "critical");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post<PriceSim>("/api/simulate/product-price", {
        product_id: selected.id, new_price: Number(newPrice),
      });
      setSim(r);
    } catch {
      toast("Simulation failed", "critical");
    } finally {
      setBusy(false);
    }
  };

  const stat = (label: string, base: string, prop: string, deltaText?: string, good?: boolean) => (
    <div className="rounded-xl border border-line p-3.5">
      <p className="text-[11px] font-medium text-muted">{label}</p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-sm tabular-nums text-muted line-through decoration-muted/60">{base}</span>
        <span className="text-lg font-semibold tabular-nums">{prop}</span>
      </div>
      {deltaText && (
        <p className={cn("text-xs font-semibold", good ? "text-[var(--delta-good)]" : "text-critical")}>{deltaText}</p>
      )}
    </div>
  );

  return (
    <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
      <div className="space-y-4">
        <Card>
          <CardTitle className="mb-4 flex items-center gap-1.5"><PackageSearch size={14} className="text-brand" /> Pick a Product Decision</CardTitle>
          <div className="space-y-3">
            <div>
              <p className="mb-1.5 text-xs font-medium text-ink-2">Product</p>
              <Select value={productId ?? ""} onChange={(e) => {
                const p = products.find((x) => x.id === Number(e.target.value));
                setProductId(Number(e.target.value));
                if (p) setNewPrice(String(p.price + 2));
                setSim(null);
              }}>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name} — ₹{p.price}</option>)}
              </Select>
            </div>
            {selected && (
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-lg border border-line p-2"><p className="font-semibold">₹{selected.price}</p><p className="text-muted">current price</p></div>
                <div className="rounded-lg border border-line p-2"><p className="font-semibold">₹{selected.cost}</p><p className="text-muted">cost</p></div>
                <div className="rounded-lg border border-line p-2"><p className="font-semibold">{num(selected.stock)}</p><p className="text-muted">in stock</p></div>
              </div>
            )}
            <div>
              <p className="mb-1.5 text-xs font-medium text-ink-2">Proposed new price (₹)</p>
              <div className="flex gap-2">
                <Input type="number" min={1} step="0.5" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} />
                <Button onClick={run} disabled={busy}>{busy ? "…" : "Predict"}</Button>
              </div>
            </div>
            {selected && (
              <div className="flex flex-wrap gap-2">
                {[-2, -1, 1, 2].map((d) => (
                  <button key={d} onClick={() => { setNewPrice(String(selected.price + d)); }}
                          className="rounded-full border border-line px-3 py-1 text-xs font-medium text-ink-2 hover:border-brand/40 hover:bg-brand-soft hover:text-brand cursor-pointer">
                    {d > 0 ? `+₹${d}` : `−₹${-d}`}
                  </button>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        {!sim ? (
          <Card className="flex h-64 items-center justify-center text-sm text-muted">
            Choose a product and press Predict — e.g. “What if I increase milk price by ₹2?”
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {stat("Price", `₹${sim.baseline.price}`, `₹${sim.proposed.price}`)}
              {stat("Demand (units/day)", String(sim.baseline.units_per_day), String(sim.proposed.units_per_day),
                    `${pct(sim.delta.demand_pct)} demand`, sim.delta.demand_pct >= 0)}
              {stat("Monthly Revenue", inr(sim.baseline.monthly_revenue), inr(sim.proposed.monthly_revenue),
                    pct(sim.delta.revenue_pct), sim.delta.revenue >= 0)}
              {stat("Monthly Gross Profit", inr(sim.baseline.monthly_gross_profit), inr(sim.proposed.monthly_gross_profit),
                    pct(sim.delta.gross_profit_pct), sim.delta.gross_profit >= 0)}
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-xl border border-line p-3.5">
                <p className="text-[11px] font-medium text-muted">Customer Satisfaction</p>
                <p className={cn("mt-1 text-lg font-semibold", sim.delta.satisfaction_pts >= 0 ? "text-[var(--delta-good)]" : "text-critical")}>
                  {sim.delta.satisfaction_pts > 0 ? "+" : ""}{sim.delta.satisfaction_pts} pts
                </p>
              </div>
              <div className="rounded-xl border border-line p-3.5">
                <p className="text-[11px] font-medium text-muted">Substitution / Churn Risk</p>
                <p className="mt-1 text-lg font-semibold">{sim.risk.substitution_pct}%</p>
              </div>
              <div className="rounded-xl border border-line p-3.5">
                <p className="text-[11px] font-medium text-muted">Stockout Risk</p>
                <p className="mt-1"><Badge tone={sim.risk.stockout === "high" ? "critical" : sim.risk.stockout === "medium" ? "medium" : "low"}>{sim.risk.stockout}</Badge></p>
              </div>
              <div className="rounded-xl border border-line p-3.5">
                <p className="text-[11px] font-medium text-muted">Days of Stock</p>
                <p className="mt-1 text-lg font-semibold tabular-nums">{sim.proposed.days_of_stock}d</p>
              </div>
            </div>

            <Card className={cn("border-l-4", sim.delta.gross_profit >= 0 ? "border-l-[var(--status-good)]" : "border-l-[var(--status-critical)]")}>
              <p className="text-sm">
                <span className="font-semibold">{sim.delta.gross_profit >= 0 ? "✅ Profitable move (predicted)." : "⚠️ This price cut costs profit."}</span>{" "}
                <span className="text-ink-2">
                  Demand is predicted to move {pct(sim.delta.demand_pct)}, gross profit {sim.delta.gross_profit >= 0 ? "up" : "down"} {inr(Math.abs(sim.delta.gross_profit))}/month.
                </span>
              </p>
            </Card>

            <HowPanel how={sim} confidence={sim.confidence_pct} />
          </>
        )}
      </div>
    </div>
  );
}

export default function SimulatorPage() {
  const { toast } = useToast();
  const [mode, setMode] = useState<"business" | "product">("business");
  const [levers, setLevers] = useState<Levers>(ZERO);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [saving, setSaving] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const run = useCallback((l: Levers) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.post<RunResponse>("/api/simulate/run", l).then(setResult).catch(() => {});
    }, 220);
  }, []);

  useEffect(() => {
    run(levers);
  }, [levers, run]);

  const set = (k: keyof Levers) => (v: number) => setLevers((s) => ({ ...s, [k]: v }));
  const reset = () => setLevers(ZERO);

  const saveScenario = async () => {
    if (!scenarioName.trim()) {
      toast("Give your scenario a name first", "critical");
      return;
    }
    setSaving(true);
    try {
      await api.post("/api/simulate/scenarios", { name: scenarioName.trim(), levers });
      toast(`Scenario "${scenarioName.trim()}" saved — compare it in Scenarios`, "good");
      setScenarioName("");
    } catch {
      toast("Failed to save scenario", "critical");
    }
    setSaving(false);
  };

  if (!result) {
    return (
      <AppShell title="Business Simulator">
        <PageSkeleton />
      </AppShell>
    );
  }

  const sim = result.simulated;
  const cur = result.current;
  const compare = [
    { metric: "Revenue", Current: cur.revenue, Simulated: sim.revenue },
    { metric: "Expenses", Current: cur.expenses, Simulated: sim.expenses },
    { metric: "Profit", Current: cur.profit, Simulated: sim.profit },
    { metric: "Cash Flow", Current: cur.cash_flow, Simulated: sim.cash_flow },
  ];

  const outcome = (label: string, value: string, delta?: number, invert = false) => {
    const good = delta === undefined ? undefined : invert ? delta <= 0 : delta >= 0;
    return (
      <div className="rounded-xl border border-line bg-surface/50 p-3.5">
        <p className="text-[11px] font-medium text-muted">{label}</p>
        <AnimatePresence mode="popLayout">
          <motion.p
            key={value}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-0.5 text-lg font-semibold tabular-nums"
          >
            {value}
          </motion.p>
        </AnimatePresence>
        {delta !== undefined && (
          <p className={cn("text-xs font-semibold", good ? "text-[var(--delta-good)]" : "text-critical")}>{pct(delta)}</p>
        )}
      </div>
    );
  };

  return (
    <AppShell title="AI Business Simulator">
      {/* mode switch */}
      <div className="mb-5 inline-flex rounded-xl border border-line p-1">
        {([["business", "Business Levers"], ["product", "Product Price"]] as const).map(([key, label]) => (
          <button key={key} onClick={() => setMode(key)}
                  className={cn("rounded-lg px-4 py-1.5 text-xs font-semibold transition-all cursor-pointer",
                                mode === key ? "bg-gradient-to-r from-brand/15 to-brand-2/10 text-brand shadow-sm" : "text-ink-2 hover:text-ink")}>
            {label}
          </button>
        ))}
      </div>

      {mode === "product" ? <ProductPriceMode /> : (
      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        {/* levers panel */}
        <div className="space-y-4">
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <CardTitle className="flex items-center gap-1.5"><FlaskConical size={14} className="text-brand" /> Decision Levers</CardTitle>
              <Button variant="ghost" size="sm" onClick={reset}><RotateCcw size={13} /> Reset</Button>
            </div>
            <div className="space-y-5">
              <Slider label="Product Price" value={levers.price_change_pct} min={-30} max={30} onChange={set("price_change_pct")} />
              <Slider label="Marketing Budget" value={levers.marketing_change_pct} min={-50} max={200} step={5} onChange={set("marketing_change_pct")} />
              <Slider label="Employees" value={levers.employee_delta} min={-5} max={10} unit="" onChange={set("employee_delta")} />
              <Slider label="Discount" value={levers.discount_pct} min={0} max={40} onChange={set("discount_pct")} />
              <Slider label="Inventory Purchase" value={levers.inventory_change_pct} min={-50} max={100} step={5} onChange={set("inventory_change_pct")} />
              <Slider label="Store Timing" value={levers.hours_delta} min={-4} max={6} step={0.5} unit="h" onChange={set("hours_delta")} />
              <Slider label="Supplier Cost" value={levers.supplier_cost_change_pct} min={-20} max={20} onChange={set("supplier_cost_change_pct")} />
              <Slider label="Operating Expenses" value={levers.opex_change_pct} min={-30} max={30} onChange={set("opex_change_pct")} />
            </div>
          </Card>

          <Card>
            <CardTitle className="mb-3 flex items-center gap-1.5"><Zap size={14} className="text-brand" /> Quick What-Ifs</CardTitle>
            <div className="flex flex-wrap gap-2">
              {WHAT_IFS.map((w) => (
                <button
                  key={w.label}
                  onClick={() => setLevers({ ...ZERO, ...w.levers })}
                  className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink-2 transition-all hover:border-brand/40 hover:bg-brand-soft hover:text-brand cursor-pointer"
                >
                  {w.label}
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <CardTitle className="mb-3 flex items-center gap-1.5"><Save size={14} className="text-brand" /> Save as Scenario</CardTitle>
            <div className="flex gap-2">
              <Input placeholder="e.g. Diwali strategy" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} />
              <Button onClick={saveScenario} disabled={saving}>Save</Button>
            </div>
          </Card>
        </div>

        {/* results panel */}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {outcome("Monthly Revenue", inr(sim.revenue), sim.deltas.revenue_pct)}
            {outcome("Monthly Profit", inr(sim.profit), sim.deltas.profit_pct)}
            {outcome("Expenses", inr(sim.expenses), sim.deltas.expenses_pct, true)}
            {outcome("Customers", num(sim.customers), sim.deltas.customers_pct)}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {outcome("Cash Flow", inr(sim.cash_flow))}
            {outcome("Satisfaction", `${sim.satisfaction}%`)}
            {outcome("Churn Risk", `${sim.churn_risk_pct}%`)}
            {outcome("Inventory Days", `${sim.inventory_days}d`)}
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_auto]">
            <Card>
              <CardTitle className="mb-3">Current vs Simulated</CardTitle>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={compare} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="30%" barGap={3}>
                  <CartesianGrid strokeDasharray="3 6" stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="metric" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={{ stroke: "var(--grid)" }} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} tickFormatter={(v) => inr(Number(v))} width={56} />
                  <Tooltip
                    contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }}
                    cursor={{ fill: "var(--brand-soft)" }}
                    formatter={(v, name) => [inr(Number(v)), String(name)]}
                  />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />
                  <Bar dataKey="Current" fill={SERIES[0]} radius={[4, 4, 0, 0]} animationDuration={500} />
                  <Bar dataKey="Simulated" fill={SERIES[4]} radius={[4, 4, 0, 0]} animationDuration={500} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card className="flex flex-col items-center justify-center gap-5 px-8">
              <Gauge value={sim.health_score} size={110} label="Business Health" />
              <div className="flex flex-col items-center">
                <Badge tone={sim.risk_score > 60 ? "critical" : sim.risk_score > 35 ? "medium" : "low"}>
                  Risk {Math.round(sim.risk_score)}/100
                </Badge>
                <p className="mt-2 max-w-[160px] text-center text-[11px] text-muted">
                  {sim.risk_score > 60 ? "High-risk move — test a softer version." : sim.risk_score > 35 ? "Moderate risk — monitor closely." : "Low risk — safe to execute."}
                </p>
              </div>
            </Card>
          </div>

          {/* verdict strip */}
          <Card className={cn("border-l-4", sim.profit >= cur.profit ? "border-l-[var(--status-good)]" : "border-l-[var(--status-critical)]")}>
            <p className="text-sm">
              <span className="font-semibold">{sim.profit >= cur.profit ? "✅ This move looks profitable." : "⚠️ This move reduces profit."}</span>{" "}
              <span className="text-ink-2">
                Projected profit changes from {inr(cur.profit)} to <strong className="text-ink">{inr(sim.profit)}</strong> ({pct(sim.deltas.profit_pct)}), with customer base moving {pct(sim.deltas.customers_pct)} and satisfaction at {sim.satisfaction}%.
                {sim.cash_flow < 0 && " Warning: cash flow goes negative this month due to upfront inventory spend."}
              </span>
            </p>
          </Card>

          {result.how && <HowPanel how={result.how} />}
        </div>
      </div>
      )}
    </AppShell>
  );
}
