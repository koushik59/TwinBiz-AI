"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, EmptyState, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, shortDate } from "@/lib/utils";
import { motion } from "framer-motion";
import { CalendarDays, PartyPopper, Radar, Recycle, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

type Opportunity = {
  kind: string; title: string; when: string | null; days_away: number | null;
  expected_boost_pct: number | null; expected_extra_revenue: number | null;
  suggested_products: string[]; evidence: string; action: string;
};
type Result = { opportunities: Opportunity[]; label: string };

const KIND_ICON = { festival: PartyPopper, weekday: CalendarDays, category: TrendingUp, clearance: Recycle } as const;

export default function OpportunitiesPage() {
  const [data, setData] = useState<Result | null>(null);

  useEffect(() => {
    api.get<Result>("/api/intel/opportunities").then(setData).catch(() => {});
  }, []);

  if (!data) return <AppShell title="Opportunity Radar"><PageSkeleton /></AppShell>;

  return (
    <AppShell title="Opportunity Radar">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <p className="max-w-2xl text-sm text-ink-2">
          The Risk Analyzer finds problems — this radar finds upside: upcoming demand windows,
          your strongest days, rising categories and locked capital, each sized from your own history.
        </p>

        {data.opportunities.length === 0 ? (
          <EmptyState icon={Radar} title="No clear opportunities detected yet"
            hint="The radar needs a few weeks of history to spot demand windows and trends." />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {data.opportunities.map((o, i) => {
              const Icon = KIND_ICON[o.kind as keyof typeof KIND_ICON] ?? Radar;
              return (
                <motion.div key={`${o.kind}-${o.title}`} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}>
                  <Card className="flex h-full flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="rounded-xl bg-brand-soft p-2 text-brand"><Icon size={16} /></div>
                        <div>
                          <p className="font-semibold leading-snug">{o.title}</p>
                          {o.when && (
                            <p className="text-[11px] text-muted">{shortDate(o.when)} · in {o.days_away} days</p>
                          )}
                        </div>
                      </div>
                      {o.expected_boost_pct !== null && <Badge tone="good">+{o.expected_boost_pct}%</Badge>}
                    </div>

                    <p className="mt-3 text-sm leading-relaxed text-ink-2">
                      <span className="font-medium text-ink">Evidence:</span> {o.evidence}
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-ink-2">
                      <span className="font-medium text-ink">Play:</span> {o.action}
                    </p>
                    {o.suggested_products.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {o.suggested_products.map((p) => (
                          <span key={p} className="rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-2">{p}</span>
                        ))}
                      </div>
                    )}
                    {o.expected_extra_revenue !== null && o.expected_extra_revenue > 0 && (
                      <p className="mt-auto pt-4 text-sm font-bold text-[var(--delta-good)]">
                        Potential ≈ {inr(o.expected_extra_revenue)}
                      </p>
                    )}
                  </Card>
                </motion.div>
              );
            })}
          </div>
        )}
        <p className="text-[11px] text-muted">{data.label}</p>
      </motion.div>
    </AppShell>
  );
}
