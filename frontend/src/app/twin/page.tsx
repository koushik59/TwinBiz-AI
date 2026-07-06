"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, num } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { Boxes, Package, Truck, User2, X } from "lucide-react";
import { useEffect, useState } from "react";

type TwinProduct = {
  id: number; name: string; category: string; price: number; cost: number; stock: number;
  reorder_level: number; daily_demand: number; margin_pct: number; days_of_stock: number;
  stock_value: number; status: string;
};
type TwinEmployee = { id: number; name: string; role: string; salary: number; department: string; performance: number };
type TwinSupplier = { id: number; name: string; category: string; reliability: number; lead_time_days: number; cost_index: number };
type Twin = {
  business: { name: string; business_type: string; location: string; employees_count: number; monthly_revenue: number; monthly_expenses: number; working_hours: string };
  products: TwinProduct[];
  employees: TwinEmployee[];
  suppliers: TwinSupplier[];
};

type Selected =
  | { kind: "product"; item: TwinProduct }
  | { kind: "employee"; item: TwinEmployee }
  | { kind: "supplier"; item: TwinSupplier }
  | null;

const statusColor: Record<string, string> = {
  healthy: "bg-good/15 border-good/40",
  low: "bg-warning/15 border-warning/50",
  critical: "bg-critical/15 border-critical/50",
  overstock: "bg-serious/15 border-serious/40",
};

export default function TwinPage() {
  const [twin, setTwin] = useState<Twin | null>(null);
  const [selected, setSelected] = useState<Selected>(null);

  useEffect(() => {
    api.get<Twin>("/api/business/twin").then(setTwin).catch(() => {});
  }, []);

  if (!twin) {
    return (
      <AppShell title="Digital Twin"><PageSkeleton /></AppShell>
    );
  }

  const categories = [...new Set(twin.products.map((p) => p.category))];

  return (
    <AppShell title="Digital Twin">
      <p className="mb-4 text-sm text-ink-2">
        A live virtual replica of <strong className="text-ink">{twin.business.name}</strong>. Click any shelf, employee or supplier to inspect its live metrics.
      </p>
      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <div className="space-y-5">
          {/* store layout: departments as shelves */}
          <Card>
            <CardTitle className="mb-3 flex items-center gap-1.5"><Boxes size={14} className="text-brand" /> Store Layout — Departments & Shelves</CardTitle>
            <div className="grid gap-4 sm:grid-cols-2">
              {categories.map((cat) => (
                <div key={cat} className="rounded-2xl border border-line p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{cat}</p>
                  <div className="grid grid-cols-2 gap-2">
                    {twin.products.filter((p) => p.category === cat).map((p) => (
                      <motion.button
                        key={p.id}
                        whileHover={{ scale: 1.03 }}
                        whileTap={{ scale: 0.97 }}
                        onClick={() => setSelected({ kind: "product", item: p })}
                        className={cn(
                          "rounded-xl border p-2.5 text-left transition-shadow hover:shadow-md cursor-pointer",
                          statusColor[p.status] ?? "border-line"
                        )}
                      >
                        <div className="flex items-center gap-1.5">
                          <Package size={13} className="shrink-0 text-ink-2" />
                          <p className="truncate text-xs font-medium">{p.name}</p>
                        </div>
                        <p className="mt-1 text-[11px] text-ink-2">{num(p.stock)} in stock · {p.days_of_stock}d left</p>
                      </motion.button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-muted">
              {[["healthy", "Healthy"], ["low", "Low stock"], ["critical", "Critical"], ["overstock", "Overstock"]].map(([k, label]) => (
                <span key={k} className="flex items-center gap-1.5">
                  <span className={cn("h-2.5 w-2.5 rounded-full border", statusColor[k])} /> {label}
                </span>
              ))}
            </div>
          </Card>

          <div className="grid gap-5 md:grid-cols-2">
            {/* team */}
            <Card>
              <CardTitle className="mb-3 flex items-center gap-1.5"><User2 size={14} className="text-brand" /> Team ({twin.employees.length})</CardTitle>
              <div className="space-y-2">
                {twin.employees.map((e) => (
                  <button
                    key={e.id}
                    onClick={() => setSelected({ kind: "employee", item: e })}
                    className="flex w-full items-center gap-3 rounded-xl border border-line p-2.5 text-left transition-colors hover:bg-brand-soft cursor-pointer"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand/25 to-brand-2/25 text-xs font-bold text-brand">
                      {e.name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{e.name}</p>
                      <p className="text-xs text-muted">{e.role} · {e.department}</p>
                    </div>
                    <div className="h-1.5 w-14 overflow-hidden rounded-full bg-grid">
                      <div className="h-full rounded-full bg-gradient-to-r from-brand to-brand-2" style={{ width: `${e.performance * 100}%` }} />
                    </div>
                  </button>
                ))}
              </div>
            </Card>

            {/* suppliers */}
            <Card>
              <CardTitle className="mb-3 flex items-center gap-1.5"><Truck size={14} className="text-brand" /> Suppliers ({twin.suppliers.length})</CardTitle>
              <div className="space-y-2">
                {twin.suppliers.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelected({ kind: "supplier", item: s })}
                    className="flex w-full items-center justify-between rounded-xl border border-line p-3 text-left transition-colors hover:bg-brand-soft cursor-pointer"
                  >
                    <div>
                      <p className="text-sm font-medium">{s.name}</p>
                      <p className="text-xs text-muted">{s.category} · {s.lead_time_days}d lead time</p>
                    </div>
                    <Badge tone={s.reliability > 0.9 ? "good" : s.reliability > 0.8 ? "medium" : "critical"}>
                      {Math.round(s.reliability * 100)}% reliable
                    </Badge>
                  </button>
                ))}
              </div>
            </Card>
          </div>
        </div>

        {/* inspector panel */}
        <div className="xl:sticky xl:top-20 xl:self-start">
          <AnimatePresence mode="wait">
            {selected ? (
              <motion.div key={`${selected.kind}-${(selected.item as { id: number }).id}`} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }}>
                <Card>
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-ink font-semibold text-base">
                      {(selected.item as { name: string }).name}
                    </CardTitle>
                    <button onClick={() => setSelected(null)} className="text-muted hover:text-ink cursor-pointer" aria-label="Close inspector"><X size={16} /></button>
                  </div>

                  {selected.kind === "product" && (
                    <div className="mt-3 space-y-3">
                      <div className="flex gap-2">
                        <Badge tone={selected.item.status}>{selected.item.status}</Badge>
                        <Badge tone="brand">{selected.item.category}</Badge>
                      </div>
                      <dl className="grid grid-cols-2 gap-3 text-sm">
                        {[
                          ["Price", inr(selected.item.price)],
                          ["Cost", inr(selected.item.cost)],
                          ["Margin", `${selected.item.margin_pct}%`],
                          ["Stock", num(selected.item.stock)],
                          ["Daily demand", `${selected.item.daily_demand}/day`],
                          ["Days of stock", `${selected.item.days_of_stock}d`],
                          ["Stock value", inr(selected.item.stock_value)],
                          ["Reorder at", num(selected.item.reorder_level)],
                        ].map(([k, v]) => (
                          <div key={k as string}>
                            <dt className="text-[11px] text-muted">{k}</dt>
                            <dd className="font-semibold tabular-nums">{v}</dd>
                          </div>
                        ))}
                      </dl>
                      <div className="rounded-xl bg-brand-soft/60 p-3 text-xs leading-relaxed text-ink-2">
                        {selected.item.status === "critical" && `⚠️ Stockout in ~${selected.item.days_of_stock} days. Order ${Math.max(Math.round(selected.item.daily_demand * 30 - selected.item.stock), 0)} units now to cover the next 30 days.`}
                        {selected.item.status === "low" && `Reorder soon — below the ${selected.item.reorder_level}-unit threshold. Fast mover at ${selected.item.daily_demand}/day.`}
                        {selected.item.status === "overstock" && `${inr(selected.item.stock_value)} locked in ${selected.item.days_of_stock} days of stock. Consider a clearance offer.`}
                        {selected.item.status === "healthy" && `Healthy: ${selected.item.days_of_stock} days of cover at current demand with a ${selected.item.margin_pct}% margin.`}
                      </div>
                    </div>
                  )}

                  {selected.kind === "employee" && (
                    <div className="mt-3 space-y-3">
                      <div className="flex gap-2">
                        <Badge tone="brand">{selected.item.role}</Badge>
                        <Badge tone="low">{selected.item.department}</Badge>
                      </div>
                      <dl className="grid grid-cols-2 gap-3 text-sm">
                        <div><dt className="text-[11px] text-muted">Salary</dt><dd className="font-semibold">{inr(selected.item.salary)}/mo</dd></div>
                        <div><dt className="text-[11px] text-muted">Performance</dt><dd className="font-semibold">{Math.round(selected.item.performance * 100)}%</dd></div>
                      </dl>
                      <div className="rounded-xl bg-brand-soft/60 p-3 text-xs leading-relaxed text-ink-2">
                        {selected.item.performance > 0.85
                          ? "⭐ Top performer — consider for shift-lead responsibilities."
                          : selected.item.performance > 0.7
                          ? "Solid contributor. Pair with a top performer during peak hours."
                          : "Below-average output — schedule a training refresher."}
                      </div>
                    </div>
                  )}

                  {selected.kind === "supplier" && (
                    <div className="mt-3 space-y-3">
                      <Badge tone="brand">{selected.item.category}</Badge>
                      <dl className="grid grid-cols-2 gap-3 text-sm">
                        <div><dt className="text-[11px] text-muted">Reliability</dt><dd className="font-semibold">{Math.round(selected.item.reliability * 100)}%</dd></div>
                        <div><dt className="text-[11px] text-muted">Lead time</dt><dd className="font-semibold">{selected.item.lead_time_days} days</dd></div>
                        <div><dt className="text-[11px] text-muted">Cost index</dt><dd className="font-semibold">{selected.item.cost_index}× market</dd></div>
                      </dl>
                      <div className="rounded-xl bg-brand-soft/60 p-3 text-xs leading-relaxed text-ink-2">
                        {selected.item.cost_index > 1.05
                          ? `Charging ${Math.round((selected.item.cost_index - 1) * 100)}% above market — renegotiate or run the "cheaper supplier" simulation.`
                          : selected.item.reliability < 0.85
                          ? "Reliability is shaky — keep a backup supplier for festival seasons."
                          : "Good value and dependable. Consider consolidating more volume here."}
                      </div>
                    </div>
                  )}
                </Card>
              </motion.div>
            ) : (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Card className="border-dashed text-center">
                  <p className="py-8 text-sm text-muted">Select any entity in the twin<br />to inspect live metrics & AI advice.</p>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* financial overview */}
          <Card className="mt-4">
            <CardTitle className="mb-3">Financial Overview</CardTitle>
            <dl className="space-y-2.5 text-sm">
              {[
                ["Type", twin.business.business_type],
                ["Location", twin.business.location || "—"],
                ["Hours", twin.business.working_hours],
                ["Monthly revenue", inr(twin.business.monthly_revenue)],
                ["Monthly expenses", inr(twin.business.monthly_expenses)],
                ["Inventory value", inr(twin.products.reduce((a, p) => a + p.stock_value, 0))],
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between">
                  <dt className="text-muted">{k}</dt>
                  <dd className="font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
