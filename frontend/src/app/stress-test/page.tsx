"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr } from "@/lib/utils";
import { motion } from "framer-motion";
import { ChevronDown, Info, LifeBuoy, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

type Scenario = {
  key: string; title: string; description: string;
  baseline: { revenue: number; expenses: number; profit: number };
  stressed: { revenue: number; expenses: number; profit: number };
  monthly_cash_impact: number; lost_sales: number;
  survival_months: number | null; survives: boolean;
  stock_days_under_stress: number; served_demand_pct: number;
  recovery_strategy: string; assumptions: string[]; label: string;
};
type Result = { scenarios: Scenario[]; summary: { tested: number; survived: number; weakest: string } };

export default function StressTestPage() {
  const [data, setData] = useState<Result | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.get<Result>("/api/intel/stress-tests").then(setData).catch(() => {});
  }, []);

  if (!data) return <AppShell title="Stress Test Simulator"><PageSkeleton /></AppShell>;

  return (
    <AppShell title="Stress Test Simulator">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Card className="flex items-center gap-3 px-4 py-3">
            <ShieldCheck size={18} className="text-[var(--delta-good)]" />
            <div>
              <p className="text-lg font-bold leading-none">{data.summary.survived}/{data.summary.tested}</p>
              <p className="text-[11px] text-muted">scenarios survived</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 px-4 py-3">
            <ShieldAlert size={18} className="text-critical" />
            <div>
              <p className="text-sm font-semibold leading-tight">{data.summary.weakest}</p>
              <p className="text-[11px] text-muted">hits your business hardest</p>
            </div>
          </Card>
          <p className="max-w-md text-xs leading-relaxed text-muted">
            Banking-style shock tests run on your twin&apos;s last 30 days. Each scenario shows the monthly
            damage, how long you&apos;d survive, and a recovery playbook.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {data.scenarios.map((s, i) => {
            const dmg = s.monthly_cash_impact;
            return (
              <motion.div key={s.key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
                <Card className="h-full">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{s.title}</p>
                      <p className="mt-0.5 text-xs text-ink-2">{s.description}</p>
                    </div>
                    <Badge tone={s.survives ? "good" : "critical"}>
                      {s.survives ? "Survives" : "At risk"}
                    </Badge>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-xl bg-brand-soft/50 p-2.5">
                      <p className={cn("text-sm font-bold", dmg < 0 ? "text-critical" : "text-[var(--delta-good)]")}>{inr(dmg)}</p>
                      <p className="text-[10px] text-muted">monthly cash impact</p>
                    </div>
                    <div className="rounded-xl bg-brand-soft/50 p-2.5">
                      <p className="text-sm font-bold">
                        {s.survival_months === null ? "∞" : `${s.survival_months} mo`}
                      </p>
                      <p className="text-[10px] text-muted">survival time</p>
                    </div>
                    <div className="rounded-xl bg-brand-soft/50 p-2.5">
                      <p className="text-sm font-bold">{s.served_demand_pct}%</p>
                      <p className="text-[10px] text-muted">demand served</p>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-xs text-ink-2">
                    <span>Profit: <strong className="text-ink">{inr(s.baseline.profit)}</strong> → <strong className={s.stressed.profit < 0 ? "text-critical" : "text-ink"}>{inr(s.stressed.profit)}</strong></span>
                    <span>Stock cover: {s.stock_days_under_stress}d</span>
                  </div>

                  <div className="mt-3 flex items-start gap-2 rounded-xl border border-line p-3">
                    <LifeBuoy size={14} className="mt-0.5 shrink-0 text-brand" />
                    <p className="text-xs leading-relaxed text-ink-2"><strong className="text-ink">Recovery:</strong> {s.recovery_strategy}</p>
                  </div>

                  <button onClick={() => setOpen(open === s.key ? null : s.key)}
                    className="mt-2.5 flex w-full items-center justify-between text-left text-[11px] font-medium text-muted cursor-pointer hover:text-ink">
                    <span className="flex items-center gap-1"><Info size={11} /> Assumptions</span>
                    <ChevronDown size={12} className={cn("transition-transform", open === s.key && "rotate-180")} />
                  </button>
                  {open === s.key && (
                    <ul className="mt-1.5 space-y-1 text-[11px] leading-relaxed text-muted">
                      {s.assumptions.map((a, j) => <li key={j}>• {a}</li>)}
                    </ul>
                  )}
                </Card>
              </motion.div>
            );
          })}
        </div>
        <p className="text-[11px] text-muted">Every figure is predicted, not guaranteed — same deterministic engine as the Simulator.</p>
      </motion.div>
    </AppShell>
  );
}
