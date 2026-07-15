"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, EmptyState, Gauge, Input, Label, Modal, Select, useToast } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, inr, num, pct } from "@/lib/utils";
import { motion } from "framer-motion";
import { Beaker, ChevronDown, Crown, FlaskConical, Info, Percent, Rocket, Sparkles, Boxes as StockIcon, Trash2, Wand2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/* ------------------------------- types ---------------------------------- */

type Experiment = {
  id: string; product_name: string; brand: string; category: string; subcategory: string;
  description: string; unit_type: string; unit_size: string;
  supplier_cost: number; transport_cost: number; storage_cost: number; handling_cost: number;
  other_variable_cost: number; wastage_percent: number; tax_rate: number; landed_cost: number;
  min_price: number; max_price: number; price_step: number; planned_price: number;
  discount_percent: number; initial_stock: number; safety_stock: number; reorder_point: number;
  supplier_lead_time: number; marketing_budget: number; launch_date: string;
  target_segment: string; shelf_placement: string; competitor_price: number; status: string;
};

type Point = {
  price: number; discount_pct: number; effective_price: number; stock: number; marketing: number;
  landed_cost: number; predicted_units_per_day: number; predicted_demand_month: number;
  predicted_units_sold: number; unsold_inventory: number; lost_sales_units: number;
  predicted_revenue: number; predicted_gross_profit: number; net_contribution: number;
  net_3_months: number; margin_pct: number; customer_acceptance_pct: number;
  days_of_cover: number; stockout_date: string | null; stockout_risk: string; overstock_risk: string;
  break_even_units: number | null; break_even_days: number | null; break_even_months: number | null;
  investment: number; risk_score: number; risk_components: Record<string, number>;
  risk_level: string; confidence_pct: number;
  holding_cost?: number; suggested_order_qty?: number; reorder_date?: string | null;
};

type Sweep = {
  points: Point[];
  recommendations: Record<string, Point>;
  assumptions: string[]; model_version: string;
};
type InvSweep = Sweep & { monthly_demand_forecast: number; recommended_stock: number; recommended_reason: string };
type Optimize = {
  evaluated: number; feasible: number; error?: string;
  strategies: Record<string, Point>; assumptions: string[];
};
type Analysis = {
  point: Point;
  cannibalization: { new_product_units: number; estimated_existing_loss_units: number; net_category_growth_units: number; risk: string; affected_products: { product: string; estimated_monthly_loss_units: number }[]; assumption: string };
  timing: { windows: { month: string; festivals: string[]; demand_index: number }[]; recommended: { month: string; festivals: string[] }; note: string };
  before_after: { without: Record<string, number>; with: Record<string, number> };
  assumptions: string[];
};
type Verdict = {
  decision: string; reason: string; recommendation: string; main_risk: string;
  suggested_action: string; confidence_pct: number; source: string; narrative?: string;
};
type LabScenario = {
  id: string; name: string; price: number; discount: number; stock: number;
  marketing_budget: number; results: Point;
};

const EMPTY_FORM = {
  product_name: "", brand: "", category: "Dairy", subcategory: "", description: "",
  unit_type: "pcs", unit_size: "",
  supplier_cost: "", transport_cost: "0", storage_cost: "0", handling_cost: "0",
  other_variable_cost: "0", wastage_percent: "0", tax_rate: "0",
  min_price: "", max_price: "", price_step: "2", planned_price: "",
  discount_percent: "0", initial_stock: "100", safety_stock: "0", reorder_point: "0",
  supplier_lead_time: "3", marketing_budget: "0", launch_date: "",
  target_segment: "All Customers", shelf_placement: "Middle Shelf", competitor_price: "0",
};
type FormState = typeof EMPTY_FORM;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><Label>{label}</Label>{children}</div>;
}

function AssumptionsPanel({ assumptions, confidence }: { assumptions: string[]; confidence?: number }) {
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
        <ul className="mt-3 space-y-1.5 text-xs leading-relaxed text-ink-2">
          {assumptions.map((a, i) => <li key={i} className="flex gap-1.5"><span className="text-brand">•</span>{a}</li>)}
          <li className="pt-1 text-[11px] text-muted">Every figure is <em>predicted, not guaranteed</em>.</li>
        </ul>
      )}
    </Card>
  );
}

function RecCard({ title, point, highlight = false, extra }: { title: string; point: Point; highlight?: boolean; extra?: string }) {
  return (
    <div className={cn("rounded-xl border p-3.5", highlight ? "border-brand bg-brand-soft/50 ring-1 ring-brand/30" : "border-line")}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-1 text-xl font-bold">₹{point.price}{point.discount_pct > 0 ? <span className="text-sm font-medium text-ink-2"> − {point.discount_pct}%</span> : null}</p>
      <p className="mt-0.5 text-xs text-ink-2">
        {num(point.predicted_units_sold)} units · {inr(point.predicted_revenue)} rev · <strong>{inr(point.predicted_gross_profit)}/mo profit</strong>
      </p>
      <p className="text-[11px] text-muted">{extra ?? `acceptance ${point.customer_acceptance_pct}% · risk ${Math.round(point.risk_score)}/100`}</p>
    </div>
  );
}

const METRICS = [
  { key: "predicted_demand_month", label: "Demand (units)", money: false },
  { key: "predicted_revenue", label: "Revenue", money: true },
  { key: "predicted_gross_profit", label: "Gross Profit / mo", money: true },
  { key: "customer_acceptance_pct", label: "Customer Acceptance %", money: false },
] as const;

/* ------------------------------ main page ------------------------------- */

export default function ProductLabPage() {
  const { toast } = useToast();
  const [experiments, setExperiments] = useState<Experiment[] | null>(null);
  const [selected, setSelected] = useState<Experiment | null>(null);
  const [options, setOptions] = useState<{ segments: string[]; placements: string[] }>({ segments: [], placements: [] });
  const [tab, setTab] = useState<"price" | "discount" | "inventory" | "strategy" | "analysis" | "scenarios">("price");

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editing, setEditing] = useState<Experiment | null>(null);
  const [saving, setSaving] = useState(false);

  const [priceSweep, setPriceSweep] = useState<Sweep | null>(null);
  const [metric, setMetric] = useState<(typeof METRICS)[number]["key"]>("predicted_gross_profit");
  const [discountSweep, setDiscountSweep] = useState<Sweep | null>(null);
  const [invSweep, setInvSweep] = useState<InvSweep | null>(null);
  const [optimizeRes, setOptimizeRes] = useState<Optimize | null>(null);
  const [constraints, setConstraints] = useState({ max_discount: "20", max_stock: "", max_marketing: "", min_margin_pct: "10" });
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [scenarios, setScenarios] = useState<{ items: LabScenario[]; highlights: Record<string, string> } | null>(null);
  const [scenarioForm, setScenarioForm] = useState({ name: "", price: "", discount: "0", stock: "", marketing_budget: "" });
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api.get<{ items: Experiment[] }>("/api/product-experiments").then((d) => {
      setExperiments(d.items);
      setSelected((cur) => d.items.find((e) => e.id === cur?.id) ?? d.items[0] ?? null);
    }).catch(() => setExperiments([]));
  }, []);

  useEffect(() => {
    load();
    api.get<{ segments: string[]; placements: string[] }>("/api/product-experiments/options").then(setOptions).catch(() => {});
  }, [load]);

  // reset per-experiment results when switching
  useEffect(() => {
    setPriceSweep(null); setDiscountSweep(null); setInvSweep(null);
    setOptimizeRes(null); setAnalysis(null); setVerdict(null); setScenarios(null);
    if (selected) {
      setScenarioForm({ name: "", price: String(selected.planned_price), discount: String(selected.discount_percent), stock: String(selected.initial_stock), marketing_budget: String(selected.marketing_budget) });
    }
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = (prefill?: Partial<FormState>) => {
    setEditing(null);
    setForm({ ...EMPTY_FORM, ...prefill });
    setModalOpen(true);
  };

  const loadDemo = async () => {
    try {
      const p = await api.get<Record<string, string | number>>("/api/product-experiments/demo-preset");
      const prefill = Object.fromEntries(Object.entries(p).map(([k, v]) => [k, String(v)])) as Partial<FormState>;
      openCreate(prefill);
      toast("Demo product loaded — Amul Protein Lassi 200ml", "good");
    } catch {
      toast("Could not load the demo preset", "critical");
    }
  };

  const saveExperiment = async () => {
    const n = (v: string) => Number(v || 0);
    const payload = {
      product_name: form.product_name.trim(), brand: form.brand.trim(), category: form.category.trim() || "General",
      subcategory: form.subcategory.trim(), description: form.description.trim(),
      unit_type: form.unit_type, unit_size: form.unit_size.trim(),
      supplier_cost: n(form.supplier_cost), transport_cost: n(form.transport_cost),
      storage_cost: n(form.storage_cost), handling_cost: n(form.handling_cost),
      other_variable_cost: n(form.other_variable_cost), wastage_percent: n(form.wastage_percent),
      tax_rate: n(form.tax_rate),
      min_price: n(form.min_price), max_price: n(form.max_price), price_step: n(form.price_step),
      planned_price: n(form.planned_price), discount_percent: n(form.discount_percent),
      initial_stock: Math.round(n(form.initial_stock)), safety_stock: Math.round(n(form.safety_stock)),
      reorder_point: Math.round(n(form.reorder_point)), supplier_lead_time: Math.round(n(form.supplier_lead_time)),
      marketing_budget: n(form.marketing_budget), launch_date: form.launch_date,
      target_segment: form.target_segment, shelf_placement: form.shelf_placement,
      competitor_price: n(form.competitor_price),
    };
    if (!payload.product_name || payload.supplier_cost <= 0 || payload.min_price <= 0 || payload.max_price <= 0 || payload.planned_price <= 0) {
      toast("Name, supplier cost and the price range are required", "critical");
      return;
    }
    setSaving(true);
    try {
      if (editing) await api.put(`/api/product-experiments/${editing.id}`, payload);
      else await api.post("/api/product-experiments", payload);
      toast(editing ? "Experiment updated" : "Experiment created — run the Price Lab", "good");
      setModalOpen(false);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Failed to save", "critical");
    } finally {
      setSaving(false);
    }
  };

  const removeExperiment = async (id: string) => {
    await api.del(`/api/product-experiments/${id}`).catch(() => {});
    setSelected(null);
    load();
  };

  const run = async (kind: string) => {
    if (!selected) return;
    setBusy(kind);
    try {
      if (kind === "price") setPriceSweep(await api.post<Sweep>(`/api/product-experiments/${selected.id}/price-sweep`));
      if (kind === "discount") setDiscountSweep(await api.post<Sweep>(`/api/product-experiments/${selected.id}/discount-sweep`, {}));
      if (kind === "inventory") setInvSweep(await api.post<InvSweep>(`/api/product-experiments/${selected.id}/inventory-sweep`, {}));
      if (kind === "strategy") {
        const c = constraints;
        setOptimizeRes(await api.post<Optimize>(`/api/product-experiments/${selected.id}/optimize`, {
          max_discount: Number(c.max_discount || 20),
          max_stock: c.max_stock ? Number(c.max_stock) : null,
          max_marketing: c.max_marketing ? Number(c.max_marketing) : null,
          min_margin_pct: Number(c.min_margin_pct || 5),
        }));
      }
      if (kind === "analysis") setAnalysis(await api.post<Analysis>(`/api/product-experiments/${selected.id}/analysis`));
      if (kind === "verdict") setVerdict(await api.post<Verdict>(`/api/product-experiments/${selected.id}/advisor`));
      if (kind === "scenarios") setScenarios(await api.get<{ items: LabScenario[]; highlights: Record<string, string> }>(`/api/product-experiments/${selected.id}/scenarios`));
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Simulation failed", "critical");
    } finally {
      setBusy(null);
    }
  };

  const saveScenario = async () => {
    if (!selected) return;
    const s = scenarioForm;
    if (!s.name.trim() || !s.price || Number(s.price) <= 0 || !s.stock || Number(s.stock) <= 0) {
      toast("Scenario needs a name, price and stock", "critical");
      return;
    }
    setBusy("save-scenario");
    try {
      await api.post(`/api/product-experiments/${selected.id}/scenarios`, {
        name: s.name.trim(), price: Number(s.price), discount: Number(s.discount || 0),
        stock: Number(s.stock), marketing_budget: Number(s.marketing_budget || 0),
      });
      toast(`Scenario "${s.name.trim()}" saved`, "good");
      setScenarioForm({ ...s, name: "" });
      run("scenarios");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Failed to save scenario", "critical");
    } finally {
      setBusy(null);
    }
  };

  /* ------------------------------ render -------------------------------- */

  if (!experiments) return <AppShell title="Product Launch Lab"><Card className="h-64 animate-pulse" /></AppShell>;

  const decisionTone: Record<string, string> = { "YES": "good", "CONDITIONAL YES": "medium", "WAIT": "high", "HIGH RISK": "critical" };
  const metricDef = METRICS.find((m) => m.key === metric)!;

  return (
    <AppShell title="Product Launch Lab">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="text-sm font-semibold">Test Before You Stock</p>
            <p className="text-xs text-muted">Simulate a completely new product inside your twin — before buying real inventory.</p>
          </div>
          <div className="ml-auto flex gap-2">
            <Button variant="outline" size="sm" onClick={loadDemo}><Wand2 size={14} /> Launch New Product Demo</Button>
            <Button size="sm" onClick={() => openCreate()}><Beaker size={14} /> Create Product Experiment</Button>
          </div>
        </div>

        {experiments.length === 0 ? (
          <EmptyState icon={Rocket} title="No product experiments yet"
            hint='Create an experiment for a product you are considering — e.g. "Amul Protein Lassi 200ml" — and TwinBiz will simulate prices, discounts, stock levels and launch strategies before you spend a rupee.'
            action={<div className="flex gap-2"><Button onClick={loadDemo}><Wand2 size={15} /> Load New Product Demo</Button><Button variant="outline" onClick={() => openCreate()}>Create manually</Button></div>} />
        ) : (
          <>
            {/* experiment selector */}
            <div className="flex flex-wrap gap-2">
              {experiments.map((e) => (
                <button key={e.id} onClick={() => setSelected(e)}
                        className={cn("flex items-center gap-2 rounded-xl border px-3.5 py-2 text-left text-xs transition-all cursor-pointer",
                                      selected?.id === e.id ? "border-brand bg-brand-soft shadow-sm" : "border-line hover:border-brand/40")}>
                  <FlaskConical size={14} className={selected?.id === e.id ? "text-brand" : "text-muted"} />
                  <span>
                    <span className="block font-semibold">{e.product_name}</span>
                    <span className="block text-muted">{e.category} · ₹{e.min_price}–₹{e.max_price} · landed ₹{e.landed_cost}</span>
                  </span>
                </button>
              ))}
            </div>

            {selected && (
              <>
                {/* tabs */}
                <div className="flex flex-wrap gap-1 rounded-xl border border-line p-1">
                  {([["price", "① Price Lab"], ["discount", "② Discount Lab"], ["inventory", "③ Inventory Lab"],
                     ["strategy", "④ Best Strategy"], ["analysis", "⑤ Launch Analysis"], ["scenarios", "⑥ Scenarios"]] as const).map(([key, label]) => (
                    <button key={key} onClick={() => setTab(key)}
                            className={cn("rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all cursor-pointer",
                                          tab === key ? "bg-gradient-to-r from-brand/15 to-brand-2/10 text-brand shadow-sm" : "text-ink-2 hover:text-ink")}>
                      {label}
                    </button>
                  ))}
                  <div className="ml-auto flex items-center gap-1 pr-1">
                    <button onClick={() => { setEditing(selected); setForm(Object.fromEntries(Object.entries(selected).map(([k, v]) => [k, String(v ?? "")])) as unknown as FormState); setModalOpen(true); }}
                            className="rounded-lg px-2 py-1 text-[11px] text-ink-2 hover:bg-brand-soft hover:text-brand cursor-pointer">Edit</button>
                    <button onClick={() => removeExperiment(selected.id)} aria-label="Delete experiment"
                            className="rounded-lg p-1.5 text-ink-2 hover:bg-critical/10 hover:text-critical cursor-pointer"><Trash2 size={13} /></button>
                  </div>
                </div>

                {/* ---------------- price lab ---------------- */}
                {tab === "price" && (
                  <div className="space-y-4">
                    <Card>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <CardTitle>Price Sweep — ₹{selected.min_price} to ₹{selected.max_price} in ₹{selected.price_step} steps</CardTitle>
                          <p className="mt-0.5 text-xs text-muted">Landed cost ₹{selected.landed_cost}/unit · initial stock {num(selected.initial_stock)} · marketing {inr(selected.marketing_budget)}</p>
                        </div>
                        <Button onClick={() => run("price")} disabled={busy === "price"}>
                          {busy === "price" ? "Simulating…" : priceSweep ? "Re-run Price Sweep" : "Run Price Sweep"}
                        </Button>
                      </div>
                    </Card>

                    {priceSweep && (
                      <>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                          <RecCard title="Best for Profit" point={priceSweep.recommendations.best_profit} />
                          <RecCard title="Best for Revenue" point={priceSweep.recommendations.best_revenue} />
                          <RecCard title="Best for Adoption" point={priceSweep.recommendations.best_adoption} />
                          <RecCard title="⭐ Best Balanced" point={priceSweep.recommendations.balanced} highlight
                                   extra="Strong demand with healthy margin and moderate risk" />
                          <RecCard title="Lowest Risk" point={priceSweep.recommendations.lowest_risk} />
                        </div>

                        <Card>
                          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                            <CardTitle>Predicted outcome by price</CardTitle>
                            <Select value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)} className="h-8 w-auto text-xs">
                              {METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
                            </Select>
                          </div>
                          <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={priceSweep.points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                              <CartesianGrid strokeDasharray="3 6" stroke="var(--grid)" vertical={false} />
                              <XAxis dataKey="price" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false}
                                     axisLine={{ stroke: "var(--grid)" }} tickFormatter={(v) => `₹${v}`} />
                              <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false}
                                     tickFormatter={(v) => metricDef.money ? inr(Number(v)) : num(Number(v))} width={60} />
                              <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }}
                                       labelFormatter={(v) => `Price ₹${v}`}
                                       formatter={(v, name) => [metricDef.money ? inr(Number(v)) : num(Number(v)), String(name)]} />
                              <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />
                              <Line type="monotone" dataKey={metric} name={metricDef.label} stroke="var(--series-1)" strokeWidth={2.5}
                                    dot={{ r: 3 }} activeDot={{ r: 5 }} animationDuration={700} />
                            </LineChart>
                          </ResponsiveContainer>
                        </Card>

                        <Card className="overflow-x-auto p-0">
                          <table className="w-full min-w-[860px] text-xs">
                            <thead>
                              <tr className="border-b border-line text-left uppercase tracking-wide text-muted">
                                {["Price", "Units/day", "Month demand", "Sold", "Revenue", "Profit/mo", "Margin", "Acceptance", "Stockout", "Break-even", "Risk"].map((h) => (
                                  <th key={h} className="px-3 py-2.5 font-semibold">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {priceSweep.points.map((p) => (
                                <tr key={p.price} className={cn("border-b border-line last:border-0",
                                    p.price === priceSweep.recommendations.balanced.price && "bg-brand-soft/40 font-semibold")}>
                                  <td className="px-3 py-2.5">₹{p.price}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.predicted_units_per_day}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(p.predicted_demand_month)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(p.predicted_units_sold)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(p.predicted_revenue)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(p.predicted_gross_profit)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.margin_pct}%</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.customer_acceptance_pct}%</td>
                                  <td className="px-3 py-2.5"><Badge tone={p.stockout_risk === "high" ? "critical" : p.stockout_risk}>{p.stockout_risk}</Badge></td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.break_even_months ? `${p.break_even_months} mo` : "—"}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{Math.round(p.risk_score)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </Card>

                        <AssumptionsPanel assumptions={priceSweep.assumptions} confidence={priceSweep.points[0]?.confidence_pct} />
                      </>
                    )}
                  </div>
                )}

                {/* ---------------- discount lab ---------------- */}
                {tab === "discount" && (
                  <div className="space-y-4">
                    <Card>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle>Discount Lab — 0% to 20% off ₹{selected.planned_price}</CardTitle>
                          <p className="mt-0.5 text-xs text-muted">How deep should the launch offer go?</p>
                        </div>
                        <Button onClick={() => run("discount")} disabled={busy === "discount"}>
                          {busy === "discount" ? "Simulating…" : "Run Discount Comparison"}
                        </Button>
                      </div>
                    </Card>
                    {discountSweep && (
                      <>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          <RecCard title="Best Profit" point={discountSweep.recommendations.best_profit} highlight />
                          <RecCard title="Best Growth" point={discountSweep.recommendations.best_growth} />
                          <RecCard title="Best Acquisition" point={discountSweep.recommendations.best_acquisition} />
                          <RecCard title="Lowest Risk" point={discountSweep.recommendations.lowest_risk} />
                        </div>
                        <Card className="overflow-x-auto p-0">
                          <table className="w-full min-w-[760px] text-xs">
                            <thead>
                              <tr className="border-b border-line text-left uppercase tracking-wide text-muted">
                                {["Discount", "Final price", "Demand", "Sold", "Revenue", "Profit/mo", "Margin", "Acceptance", "Stockout", "Required stock"].map((h) => (
                                  <th key={h} className="px-3 py-2.5 font-semibold">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {discountSweep.points.map((p) => (
                                <tr key={p.discount_pct} className="border-b border-line last:border-0">
                                  <td className="px-3 py-2.5 font-semibold">{p.discount_pct}%</td>
                                  <td className="px-3 py-2.5">₹{p.effective_price}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(p.predicted_demand_month)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(p.predicted_units_sold)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(p.predicted_revenue)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(p.predicted_gross_profit)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.margin_pct}%</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.customer_acceptance_pct}%</td>
                                  <td className="px-3 py-2.5"><Badge tone={p.stockout_risk === "high" ? "critical" : p.stockout_risk}>{p.stockout_risk}</Badge></td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(p.predicted_demand_month)} units</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </Card>
                        <AssumptionsPanel assumptions={discountSweep.assumptions} confidence={discountSweep.points[0]?.confidence_pct} />
                      </>
                    )}
                  </div>
                )}

                {/* ---------------- inventory lab ---------------- */}
                {tab === "inventory" && (
                  <div className="space-y-4">
                    <Card>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle>Inventory Lab — how much stock should the first order be?</CardTitle>
                          <p className="mt-0.5 text-xs text-muted">Supplier lead time {selected.supplier_lead_time}d · safety stock {selected.safety_stock} · reorder point {selected.reorder_point}</p>
                        </div>
                        <Button onClick={() => run("inventory")} disabled={busy === "inventory"}>
                          {busy === "inventory" ? "Simulating…" : "Run Inventory Simulation"}
                        </Button>
                      </div>
                    </Card>
                    {invSweep && (
                      <>
                        <Card className="border-l-4 border-l-[var(--status-good)]">
                          <p className="text-sm">
                            <StockIcon size={15} className="mr-1 inline text-brand" />
                            <span className="font-semibold">Best initial stock: {num(invSweep.recommended_stock)} units.</span>{" "}
                            <span className="text-ink-2">{invSweep.recommended_reason} Forecast month-1 demand: {num(invSweep.monthly_demand_forecast)} units.</span>
                          </p>
                        </Card>
                        <Card className="overflow-x-auto p-0">
                          <table className="w-full min-w-[820px] text-xs">
                            <thead>
                              <tr className="border-b border-line text-left uppercase tracking-wide text-muted">
                                {["Stock", "Days of cover", "Stockout date", "Lost sales", "Unsold", "Holding cost", "Reorder date", "Order qty", "Stockout", "Overstock"].map((h) => (
                                  <th key={h} className="px-3 py-2.5 font-semibold">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {invSweep.points.map((p) => (
                                <tr key={p.stock} className={cn("border-b border-line last:border-0", p.stock === invSweep.recommended_stock && "bg-brand-soft/40 font-semibold")}>
                                  <td className="px-3 py-2.5">{num(p.stock)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.days_of_cover}d</td>
                                  <td className="px-3 py-2.5">{p.stockout_date ?? "—"}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.lost_sales_units > 0 ? `${num(p.lost_sales_units)} units` : "—"}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{p.unsold_inventory > 0 ? num(p.unsold_inventory) : "—"}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(p.holding_cost ?? 0)}/mo</td>
                                  <td className="px-3 py-2.5">{p.reorder_date ?? "—"}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(p.suggested_order_qty ?? 0)}</td>
                                  <td className="px-3 py-2.5"><Badge tone={p.stockout_risk === "high" ? "critical" : p.stockout_risk}>{p.stockout_risk}</Badge></td>
                                  <td className="px-3 py-2.5"><Badge tone={p.overstock_risk === "high" ? "critical" : p.overstock_risk === "medium" ? "medium" : "low"}>{p.overstock_risk}</Badge></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </Card>
                        <AssumptionsPanel assumptions={invSweep.assumptions} confidence={invSweep.points[0]?.confidence_pct} />
                      </>
                    )}
                  </div>
                )}

                {/* ---------------- best strategy ---------------- */}
                {tab === "strategy" && (
                  <div className="space-y-4">
                    <Card>
                      <CardTitle className="mb-3 flex items-center gap-1.5"><Sparkles size={14} className="text-brand" /> Find Best Launch Strategy</CardTitle>
                      <p className="mb-3 text-xs text-muted">Deterministic grid search across price × discount × stock × marketing within your constraints (3-month horizon).</p>
                      <div className="grid gap-3 sm:grid-cols-4">
                        <Field label="Max Discount (%)"><Input type="number" min={0} max={100} value={constraints.max_discount} onChange={(e) => setConstraints({ ...constraints, max_discount: e.target.value })} /></Field>
                        <Field label="Max Initial Stock"><Input type="number" min={1} placeholder={`default ${selected.initial_stock * 2}`} value={constraints.max_stock} onChange={(e) => setConstraints({ ...constraints, max_stock: e.target.value })} /></Field>
                        <Field label="Max Marketing (₹)"><Input type="number" min={0} placeholder={`default ${Math.max(selected.marketing_budget, 5000)}`} value={constraints.max_marketing} onChange={(e) => setConstraints({ ...constraints, max_marketing: e.target.value })} /></Field>
                        <Field label="Min Margin (%)"><Input type="number" min={0} max={90} value={constraints.min_margin_pct} onChange={(e) => setConstraints({ ...constraints, min_margin_pct: e.target.value })} /></Field>
                      </div>
                      <div className="mt-4">
                        <Button onClick={() => run("strategy")} disabled={busy === "strategy"}>
                          {busy === "strategy" ? "Searching…" : "Find Best Launch Strategy"}
                        </Button>
                      </div>
                    </Card>
                    {optimizeRes && !optimizeRes.error && (
                      <>
                        <p className="text-xs text-muted">Evaluated {num(optimizeRes.evaluated)} combinations · {num(optimizeRes.feasible)} met your margin floor</p>
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                          {([["recommended", "⭐ Recommended Balanced", true], ["max_profit", "Maximum Profit", false],
                             ["max_growth", "Maximum Growth", false], ["lowest_risk", "Lowest Risk", false]] as const).map(([key, title, hl]) => {
                            const s = optimizeRes.strategies[key];
                            return (
                              <div key={key} className={cn("rounded-xl border p-4", hl ? "border-brand bg-brand-soft/50 ring-1 ring-brand/30" : "border-line")}>
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</p>
                                <p className="mt-1.5 text-2xl font-bold">₹{s.price}</p>
                                <dl className="mt-2 space-y-1 text-xs text-ink-2">
                                  <div className="flex justify-between"><dt>Discount</dt><dd className="font-semibold">{s.discount_pct}%</dd></div>
                                  <div className="flex justify-between"><dt>Initial stock</dt><dd className="font-semibold">{num(s.stock)} units</dd></div>
                                  <div className="flex justify-between"><dt>Marketing</dt><dd className="font-semibold">{inr(s.marketing)}</dd></div>
                                  <div className="flex justify-between border-t border-line pt-1"><dt>Revenue (mo 1)</dt><dd className="font-semibold">{inr(s.predicted_revenue)}</dd></div>
                                  <div className="flex justify-between"><dt>Profit /mo</dt><dd className="font-semibold">{inr(s.predicted_gross_profit)}</dd></div>
                                  <div className="flex justify-between"><dt>Net over 3 mo</dt><dd className="font-semibold">{inr(s.net_3_months)}</dd></div>
                                </dl>
                                <div className="mt-2 flex gap-1.5">
                                  <Badge tone={s.risk_score > 60 ? "critical" : s.risk_score > 35 ? "medium" : "low"}>Risk {Math.round(s.risk_score)}</Badge>
                                  <Badge tone="brand">Conf {s.confidence_pct}%</Badge>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <AssumptionsPanel assumptions={optimizeRes.assumptions} />
                      </>
                    )}
                    {optimizeRes?.error && <Card className="border-warning/40 text-sm text-warning">{optimizeRes.error}</Card>}
                  </div>
                )}

                {/* ---------------- launch analysis ---------------- */}
                {tab === "analysis" && (
                  <div className="space-y-4">
                    <Card>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <CardTitle>Launch Analysis at planned ₹{selected.planned_price}{selected.discount_percent > 0 ? ` (−${selected.discount_percent}%)` : ""}</CardTitle>
                          <p className="mt-0.5 text-xs text-muted">Risk score, break-even, cannibalization, timing and the before/after twin view.</p>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" onClick={() => run("analysis")} disabled={busy === "analysis"}>{busy === "analysis" ? "Analyzing…" : "Run Analysis"}</Button>
                          <Button onClick={() => run("verdict")} disabled={busy === "verdict"}>{busy === "verdict" ? "Consulting twin…" : "Should I Launch This Product?"}</Button>
                        </div>
                      </div>
                    </Card>

                    {verdict && (
                      <Card className={cn("border-l-4", verdict.decision === "YES" ? "border-l-[var(--status-good)]" : verdict.decision === "HIGH RISK" ? "border-l-[var(--status-critical)]" : "border-l-[var(--status-warning)]")}>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={decisionTone[verdict.decision] ?? "medium"} className="text-sm">{verdict.decision}</Badge>
                          <Badge tone="brand">Confidence {verdict.confidence_pct}%</Badge>
                          <span className="text-[11px] text-muted">source: {verdict.source}</span>
                        </div>
                        <dl className="mt-3 space-y-2 text-sm">
                          <div><dt className="text-[11px] font-semibold uppercase text-muted">Reason</dt><dd className="text-ink-2">{verdict.reason}</dd></div>
                          <div><dt className="text-[11px] font-semibold uppercase text-muted">Recommendation</dt><dd className="text-ink-2">{verdict.recommendation}</dd></div>
                          <div><dt className="text-[11px] font-semibold uppercase text-muted">Main risk</dt><dd className="text-ink-2">{verdict.main_risk}</dd></div>
                          <div><dt className="text-[11px] font-semibold uppercase text-muted">Suggested action</dt><dd className="text-ink-2">{verdict.suggested_action}</dd></div>
                        </dl>
                        {verdict.narrative && <p className="mt-3 rounded-xl bg-brand-soft/60 p-3 text-xs leading-relaxed text-ink-2">{verdict.narrative}</p>}
                      </Card>
                    )}

                    {analysis && (
                      <>
                        <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
                          <Card className="flex flex-col items-center justify-center gap-3 px-8">
                            <Gauge value={100 - analysis.point.risk_score} size={110} label={`Launch Safety (risk ${Math.round(analysis.point.risk_score)}/100)`} />
                            <Badge tone={analysis.point.risk_level === "Low" ? "good" : analysis.point.risk_level === "Moderate" ? "medium" : "critical"}>{analysis.point.risk_level} risk</Badge>
                          </Card>
                          <Card>
                            <CardTitle className="mb-3">Risk components</CardTitle>
                            <div className="grid gap-2.5 sm:grid-cols-2">
                              {Object.entries(analysis.point.risk_components).map(([k, v]) => (
                                <div key={k}>
                                  <div className="mb-1 flex justify-between text-xs"><span className="capitalize text-ink-2">{k.replace("_", " ")}</span><span className="font-semibold tabular-nums">{Math.round(v)}</span></div>
                                  <div className="h-1.5 overflow-hidden rounded-full bg-grid">
                                    <div className={cn("h-full rounded-full", v > 60 ? "bg-critical" : v > 35 ? "bg-warning" : "bg-good")} style={{ width: `${Math.min(v, 100)}%` }} />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </Card>
                        </div>

                        <div className="grid gap-4 md:grid-cols-3">
                          <Card>
                            <CardTitle className="mb-2 flex items-center gap-1.5"><Percent size={13} className="text-brand" /> Break-even</CardTitle>
                            <p className="text-2xl font-bold">{analysis.point.break_even_months ? `${analysis.point.break_even_months} months` : "—"}</p>
                            <p className="mt-1 text-xs text-muted">
                              {inr(analysis.point.investment)} upfront ({num(analysis.point.stock)} units + {inr(analysis.point.marketing)} marketing) ÷ {inr(analysis.point.predicted_gross_profit)}/mo gross profit
                            </p>
                          </Card>
                          <Card>
                            <CardTitle className="mb-2">Cannibalization</CardTitle>
                            <p className="text-sm text-ink-2">
                              +{num(analysis.cannibalization.new_product_units)} new units, −{num(analysis.cannibalization.estimated_existing_loss_units)} from existing
                              {analysis.cannibalization.affected_products[0] ? ` (mostly ${analysis.cannibalization.affected_products[0].product})` : ""} →{" "}
                              <strong className="text-ink">net +{num(analysis.cannibalization.net_category_growth_units)} category units</strong>
                            </p>
                            <Badge tone={analysis.cannibalization.risk === "high" ? "critical" : analysis.cannibalization.risk} className="mt-2">{analysis.cannibalization.risk} cannibalization</Badge>
                          </Card>
                          <Card>
                            <CardTitle className="mb-2">Best launch window</CardTitle>
                            <p className="text-2xl font-bold">{analysis.timing.recommended.month}</p>
                            <p className="mt-1 text-xs text-muted">{analysis.timing.recommended.festivals.join(", ") || "No festival"} · {analysis.timing.note}</p>
                          </Card>
                        </div>

                        <Card>
                          <CardTitle className="mb-3">Business twin: WITHOUT vs WITH this launch (monthly)</CardTitle>
                          <div className="grid gap-3 sm:grid-cols-3">
                            {(["revenue", "profit", "inventory_value"] as const).map((k) => {
                              const w = analysis.before_after.without[k];
                              const a = analysis.before_after.with[k];
                              const up = a >= w;
                              return (
                                <div key={k} className="rounded-xl border border-line p-3.5">
                                  <p className="text-[11px] font-medium capitalize text-muted">{k.replace("_", " ")}</p>
                                  <div className="mt-1 flex items-baseline gap-2">
                                    <span className="text-sm tabular-nums text-muted line-through decoration-muted/60">{inr(w)}</span>
                                    <span className="text-lg font-semibold tabular-nums">{inr(a)}</span>
                                  </div>
                                  <p className={cn("text-xs font-semibold", (k === "inventory_value" ? true : up) ? "text-[var(--delta-good)]" : "text-critical")}>
                                    {pct((a / Math.max(w, 1) - 1) * 100)}
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </Card>

                        <AssumptionsPanel assumptions={analysis.assumptions} confidence={analysis.point.confidence_pct} />
                      </>
                    )}
                  </div>
                )}

                {/* ---------------- scenarios ---------------- */}
                {tab === "scenarios" && (
                  <div className="space-y-4">
                    <Card>
                      <CardTitle className="mb-3">Save a launch scenario</CardTitle>
                      <div className="grid gap-3 sm:grid-cols-5">
                        <div className="sm:col-span-1"><Field label="Name"><Input placeholder="Premium launch" value={scenarioForm.name} onChange={(e) => setScenarioForm({ ...scenarioForm, name: e.target.value })} /></Field></div>
                        <Field label="Price (₹)"><Input type="number" min={1} value={scenarioForm.price} onChange={(e) => setScenarioForm({ ...scenarioForm, price: e.target.value })} /></Field>
                        <Field label="Discount (%)"><Input type="number" min={0} max={100} value={scenarioForm.discount} onChange={(e) => setScenarioForm({ ...scenarioForm, discount: e.target.value })} /></Field>
                        <Field label="Initial stock"><Input type="number" min={1} value={scenarioForm.stock} onChange={(e) => setScenarioForm({ ...scenarioForm, stock: e.target.value })} /></Field>
                        <Field label="Marketing (₹)"><Input type="number" min={0} value={scenarioForm.marketing_budget} onChange={(e) => setScenarioForm({ ...scenarioForm, marketing_budget: e.target.value })} /></Field>
                      </div>
                      <div className="mt-3 flex gap-2">
                        <Button onClick={saveScenario} disabled={busy === "save-scenario"}>{busy === "save-scenario" ? "Simulating…" : "Simulate & Save"}</Button>
                        <Button variant="outline" onClick={() => run("scenarios")} disabled={busy === "scenarios"}>Refresh comparison</Button>
                      </div>
                    </Card>

                    {scenarios && scenarios.items.length > 0 && (
                      <Card className="overflow-x-auto p-0">
                        <table className="w-full min-w-[860px] text-xs">
                          <thead>
                            <tr className="border-b border-line text-left uppercase tracking-wide text-muted">
                              {["Scenario", "Price", "Discount", "Stock", "Marketing", "Sold", "Revenue", "Profit/mo", "Break-even", "Risk", "Confidence"].map((h) => (
                                <th key={h} className="px-3 py-2.5 font-semibold">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {scenarios.items.map((s) => {
                              const h = scenarios.highlights;
                              const tags = [
                                h.ai_recommended === s.id && "🤖 AI pick",
                                h.best_profit === s.id && "Best profit",
                                h.best_growth === s.id && "Best growth",
                                h.lowest_risk === s.id && "Lowest risk",
                              ].filter(Boolean);
                              return (
                                <tr key={s.id} className={cn("border-b border-line last:border-0", h.ai_recommended === s.id && "bg-brand-soft/40")}>
                                  <td className="px-3 py-2.5">
                                    <span className="font-semibold">{s.name}</span>
                                    {h.ai_recommended === s.id && <Crown size={12} className="ml-1 inline text-warning" />}
                                    {tags.length > 0 && <span className="block text-[10px] text-brand">{tags.join(" · ")}</span>}
                                  </td>
                                  <td className="px-3 py-2.5">₹{s.price}</td>
                                  <td className="px-3 py-2.5">{s.discount}%</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(s.stock)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(s.marketing_budget)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{num(s.results.predicted_units_sold)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(s.results.predicted_revenue)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{inr(s.results.predicted_gross_profit)}</td>
                                  <td className="px-3 py-2.5 tabular-nums">{s.results.break_even_months ? `${s.results.break_even_months} mo` : "—"}</td>
                                  <td className="px-3 py-2.5"><Badge tone={s.results.risk_score > 60 ? "critical" : s.results.risk_score > 35 ? "medium" : "low"}>{Math.round(s.results.risk_score)}</Badge></td>
                                  <td className="px-3 py-2.5 tabular-nums">{s.results.confidence_pct}%</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </Card>
                    )}
                    {scenarios && scenarios.items.length === 0 && (
                      <p className="text-center text-sm text-muted">No saved scenarios yet — try “Low Price Launch”, “Premium Launch” and “Festival Launch”.</p>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </motion.div>

      {/* create / edit modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? `Edit ${editing.product_name}` : "Create Product Experiment"} wide>
        <div className="max-h-[65vh] space-y-5 overflow-y-auto pr-1">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Basic Information</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2"><Field label="Product Name *"><Input value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} placeholder="Amul Protein Lassi 200ml" /></Field></div>
              <Field label="Brand"><Input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} /></Field>
              <Field label="Category"><Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></Field>
              <Field label="Subcategory"><Input value={form.subcategory} onChange={(e) => setForm({ ...form, subcategory: e.target.value })} /></Field>
              <Field label="Unit Size"><Input value={form.unit_size} onChange={(e) => setForm({ ...form, unit_size: e.target.value })} placeholder="200ml" /></Field>
              <div className="sm:col-span-3"><Field label="Description"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div>
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Cost per Unit (₹) — landed cost is computed automatically</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Supplier Cost *"><Input type="number" min={0} value={form.supplier_cost} onChange={(e) => setForm({ ...form, supplier_cost: e.target.value })} /></Field>
              <Field label="Transport"><Input type="number" min={0} value={form.transport_cost} onChange={(e) => setForm({ ...form, transport_cost: e.target.value })} /></Field>
              <Field label="Storage"><Input type="number" min={0} value={form.storage_cost} onChange={(e) => setForm({ ...form, storage_cost: e.target.value })} /></Field>
              <Field label="Handling"><Input type="number" min={0} value={form.handling_cost} onChange={(e) => setForm({ ...form, handling_cost: e.target.value })} /></Field>
              <Field label="Other Variable"><Input type="number" min={0} value={form.other_variable_cost} onChange={(e) => setForm({ ...form, other_variable_cost: e.target.value })} /></Field>
              <Field label="Wastage (%)"><Input type="number" min={0} max={60} value={form.wastage_percent} onChange={(e) => setForm({ ...form, wastage_percent: e.target.value })} /></Field>
              <Field label="Tax Rate (%)"><Input type="number" min={0} max={100} value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} /></Field>
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Price Experiment (simulation range — separate from real product pricing)</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Minimum Test Price *"><Input type="number" min={0} value={form.min_price} onChange={(e) => setForm({ ...form, min_price: e.target.value })} /></Field>
              <Field label="Maximum Test Price *"><Input type="number" min={0} value={form.max_price} onChange={(e) => setForm({ ...form, max_price: e.target.value })} /></Field>
              <Field label="Price Step *"><Input type="number" min={0.5} step={0.5} value={form.price_step} onChange={(e) => setForm({ ...form, price_step: e.target.value })} /></Field>
              <Field label="Planned Launch Price *"><Input type="number" min={0} value={form.planned_price} onChange={(e) => setForm({ ...form, planned_price: e.target.value })} /></Field>
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Launch Plan</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Launch Discount (%)"><Input type="number" min={0} max={100} value={form.discount_percent} onChange={(e) => setForm({ ...form, discount_percent: e.target.value })} /></Field>
              <Field label="Initial Stock"><Input type="number" min={0} value={form.initial_stock} onChange={(e) => setForm({ ...form, initial_stock: e.target.value })} /></Field>
              <Field label="Safety Stock"><Input type="number" min={0} value={form.safety_stock} onChange={(e) => setForm({ ...form, safety_stock: e.target.value })} /></Field>
              <Field label="Reorder Point"><Input type="number" min={0} value={form.reorder_point} onChange={(e) => setForm({ ...form, reorder_point: e.target.value })} /></Field>
              <Field label="Supplier Lead Time (days)"><Input type="number" min={0} value={form.supplier_lead_time} onChange={(e) => setForm({ ...form, supplier_lead_time: e.target.value })} /></Field>
              <Field label="Marketing Budget (₹)"><Input type="number" min={0} value={form.marketing_budget} onChange={(e) => setForm({ ...form, marketing_budget: e.target.value })} /></Field>
              <Field label="Target Segment">
                <Select value={form.target_segment} onChange={(e) => setForm({ ...form, target_segment: e.target.value })}>
                  {options.segments.map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Field>
              <Field label="Shelf Placement">
                <Select value={form.shelf_placement} onChange={(e) => setForm({ ...form, shelf_placement: e.target.value })}>
                  {options.placements.map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Field>
              <Field label="Competitor Price (₹, optional)"><Input type="number" min={0} value={form.competitor_price} onChange={(e) => setForm({ ...form, competitor_price: e.target.value })} /></Field>
            </div>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2 border-t border-line pt-4">
          <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
          <Button onClick={saveExperiment} disabled={saving}>{saving ? "Saving…" : editing ? "Save Changes" : "Create Experiment"}</Button>
        </div>
      </Modal>
    </AppShell>
  );
}
