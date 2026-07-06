"use client";

import { SERIES } from "@/components/charts";
import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, Gauge, Input, PageSkeleton, Slider, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, num, pct } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { FlaskConical, RotateCcw, Save, Zap } from "lucide-react";
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

const ZERO: Levers = {
  price_change_pct: 0, marketing_change_pct: 0, employee_delta: 0, discount_pct: 0,
  inventory_change_pct: 0, hours_delta: 0, supplier_cost_change_pct: 0, opex_change_pct: 0,
};

const WHAT_IFS: { label: string; levers: Partial<Levers> }[] = [
  { label: "🏷️ Increase price 10%", levers: { price_change_pct: 10 } },
  { label: "📉 Decrease price 10%", levers: { price_change_pct: -10 } },
  { label: "👥 Hire 2 employees", levers: { employee_delta: 2 } },
  { label: "🎉 Festival offer", levers: { discount_pct: 15, marketing_change_pct: 60, inventory_change_pct: 25 } },
  { label: "📣 Double marketing", levers: { marketing_change_pct: 100 } },
  { label: "📦 Reduce inventory 20%", levers: { inventory_change_pct: -20 } },
  { label: "🚚 Cheaper supplier", levers: { supplier_cost_change_pct: -8 } },
  { label: "🕘 Extend hours +2", levers: { hours_delta: 2 } },
];

export default function SimulatorPage() {
  const { toast } = useToast();
  const [levers, setLevers] = useState<Levers>(ZERO);
  const [result, setResult] = useState<{ current: SimResult; simulated: SimResult } | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [saving, setSaving] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const run = useCallback((l: Levers) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.post<{ current: SimResult; simulated: SimResult }>("/api/simulate/run", l).then(setResult).catch(() => {});
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
        </div>
      </div>
    </AppShell>
  );
}
