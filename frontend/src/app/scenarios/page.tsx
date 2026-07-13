"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, EmptyState, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { Crown, FlaskConical, GitCompareArrows, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type SimResult = {
  revenue: number; expenses: number; profit: number; customers: number;
  satisfaction: number; health_score: number; risk_score: number; inventory_value: number;
  deltas: { profit_pct: number };
};
type Scenario = { id: number; name: string; results: SimResult; created_at: string };

const ROWS: { key: keyof SimResult; label: string; fmt: (n: number) => string; higherBetter: boolean }[] = [
  { key: "revenue", label: "Revenue", fmt: inr, higherBetter: true },
  { key: "profit", label: "Profit", fmt: inr, higherBetter: true },
  { key: "expenses", label: "Expenses", fmt: inr, higherBetter: false },
  { key: "customers", label: "Customers", fmt: num, higherBetter: true },
  { key: "inventory_value", label: "Inventory", fmt: inr, higherBetter: true },
  { key: "satisfaction", label: "Satisfaction", fmt: (n) => `${n}%`, higherBetter: true },
  { key: "risk_score", label: "Risk Score", fmt: (n) => `${Math.round(n)}/100`, higherBetter: false },
  { key: "health_score", label: "Health", fmt: (n) => `${Math.round(n)}/100`, higherBetter: true },
];

type Highlights = { best_profit: number | null; best_growth: number | null; lowest_risk: number | null; ai_recommended: number | null };
type ScenariosResponse = { current: SimResult; scenarios: Scenario[]; best_id: number | null; highlights?: Highlights };

export default function ScenariosPage() {
  const [data, setData] = useState<ScenariosResponse | null>(null);

  const load = useCallback(() => {
    api.get<ScenariosResponse>("/api/simulate/scenarios").then(setData).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const remove = async (id: number) => {
    await api.del(`/api/simulate/scenarios/${id}`);
    load();
  };

  if (!data) {
    return (
      <AppShell title="Scenario Comparison"><PageSkeleton /></AppShell>
    );
  }

  const columns = [{ id: 0, name: "Current Business", results: data.current } as Scenario, ...data.scenarios.slice(0, 3)];

  return (
    <AppShell title="Scenario Comparison">
      {data.scenarios.length === 0 ? (
        <EmptyState
          icon={GitCompareArrows}
          title="No scenarios yet"
          hint="Build a strategy in the Simulator, save it as a scenario, and compare up to 3 side-by-side here."
          action={<Link href="/simulator"><Button><FlaskConical size={15} /> Open Simulator</Button></Link>}
        />
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[700px] text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="p-4 text-left text-xs font-semibold uppercase tracking-wide text-muted">Metric</th>
                  {columns.map((c) => (
                    <th key={c.id} className="p-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {c.id === data.best_id && <Crown size={14} className="text-warning" />}
                        <span className={cn("font-semibold", c.id === data.best_id && "text-brand")}>{c.name}</span>
                        {c.id !== 0 && (
                          <button onClick={() => remove(c.id)} className="text-muted transition-colors hover:text-critical cursor-pointer" aria-label={`Delete ${c.name}`}>
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                      {c.id === data.best_id && <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-warning">Best scenario</p>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => {
                  const values = columns.map((c) => c.results[row.key] as number);
                  const best = row.higherBetter ? Math.max(...values) : Math.min(...values);
                  return (
                    <tr key={row.key} className="border-b border-line last:border-0 hover:bg-brand-soft/30 transition-colors">
                      <td className="p-4 text-xs font-medium text-ink-2">{row.label}</td>
                      {columns.map((c, i) => (
                        <td key={c.id} className={cn("p-4 text-right tabular-nums", values[i] === best ? "font-bold text-[var(--delta-good)]" : "text-ink")}>
                          {row.fmt(values[i])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>

          <div className="grid gap-4 md:grid-cols-3">
            {data.scenarios.slice(0, 3).map((s) => {
              const h = data.highlights;
              const tags: { label: string; tone: string }[] = [];
              if (h?.ai_recommended === s.id) tags.push({ label: "🤖 AI Recommended", tone: "brand" });
              if (h?.best_profit === s.id) tags.push({ label: "Best for Profit", tone: "good" });
              if (h?.best_growth === s.id) tags.push({ label: "Best for Growth", tone: "medium" });
              if (h?.lowest_risk === s.id) tags.push({ label: "Lowest Risk", tone: "low" });
              return (
                <Card key={s.id} className={cn(h?.ai_recommended === s.id && "ring-2 ring-brand")}>
                  <div className="flex items-center justify-between">
                    <CardTitle>{s.name}</CardTitle>
                    {s.id === data.best_id && <Crown size={14} className="text-warning" />}
                  </div>
                  <p className="mt-2 text-2xl font-bold">{inr(s.results.profit)}</p>
                  <p className="text-xs text-muted">projected monthly profit ({s.results.deltas.profit_pct > 0 ? "+" : ""}{s.results.deltas.profit_pct}% vs current)</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {tags.map((t) => <Badge key={t.label} tone={t.tone}>{t.label}</Badge>)}
                    <Badge tone={s.results.risk_score > 60 ? "critical" : s.results.risk_score > 35 ? "medium" : "low"}>Risk {Math.round(s.results.risk_score)}</Badge>
                  </div>
                </Card>
              );
            })}
          </div>
        </motion.div>
      )}
    </AppShell>
  );
}
