"use client";

import { TrendArea } from "@/components/charts";
import { AppShell } from "@/components/shell";
import { Card, CardTitle, PageSkeleton, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { HeartHandshake, TrendingDown, UserPlus, Users } from "lucide-react";
import { useEffect, useState } from "react";

type Customers = {
  trend: { day: string; customers: number; new_customers: number; returning: number }[];
  summary: { monthly_customers: number; new_customers: number; retention_pct: number; churn_pct: number; avg_ticket: number; clv: number };
  segments?: { name: string; share_pct: number; behaviour: string }[];
  predictions?: { return_probability_pct: number; discount_response: string; price_increase_response: string; new_product_adoption_pct: number; label: string };
};

export default function CustomersPage() {
  const [data, setData] = useState<Customers | null>(null);

  useEffect(() => {
    api.get<Customers>("/api/analytics/customers").then(setData).catch(() => {});
  }, []);

  if (!data) {
    return (
      <AppShell title="Customer Analytics"><PageSkeleton /></AppShell>
    );
  }

  const s = data.summary;

  return (
    <AppShell title="Customer Analytics">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatTile label="Monthly Visits" value={num(s.monthly_customers)} icon={Users} />
          <StatTile label="New Customers (30d)" value={num(s.new_customers)} icon={UserPlus} />
          <StatTile label="Retention Rate" value={`${s.retention_pct}%`} icon={HeartHandshake} hint={`Churn: ${s.churn_pct}%`} />
          <StatTile label="Customer Lifetime Value" value={inr(s.clv)} icon={TrendingDown} hint={`Avg ticket ${inr(s.avg_ticket)}`} />
        </div>

        <Card>
          <CardTitle className="mb-3">New vs Returning Customers (180 days)</CardTitle>
          <TrendArea
            data={data.trend}
            x="day"
            series={[
              { key: "returning", label: "Returning" },
              { key: "new_customers", label: "New" },
            ]}
            money={false}
            height={320}
          />
        </Card>

        {data.segments && (
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <CardTitle>Customer Segments</CardTitle>
                <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted">Aggregate estimate</span>
              </div>
              <div className="space-y-2.5">
                {data.segments.map((seg) => (
                  <div key={seg.name}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="font-semibold">{seg.name}</span>
                      <span className="tabular-nums text-ink-2">~{seg.share_pct}%</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-grid">
                      <div className="h-full rounded-full bg-gradient-to-r from-brand to-brand-2" style={{ width: `${Math.min(seg.share_pct, 100)}%` }} />
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted">{seg.behaviour}</p>
                  </div>
                ))}
              </div>
            </Card>
            {data.predictions && (
              <Card>
                <CardTitle className="mb-3">Behaviour Predictions</CardTitle>
                <dl className="space-y-3 text-sm">
                  <div className="flex items-center justify-between rounded-xl border border-line p-3">
                    <dt className="text-xs text-ink-2">Probability of return (30d)</dt>
                    <dd className="text-lg font-bold tabular-nums">{data.predictions.return_probability_pct}%</dd>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-line p-3">
                    <dt className="text-xs text-ink-2">New product adoption potential</dt>
                    <dd className="text-lg font-bold tabular-nums">{data.predictions.new_product_adoption_pct}%</dd>
                  </div>
                  <div className="rounded-xl border border-line p-3">
                    <dt className="text-xs font-semibold">Discount response</dt>
                    <dd className="mt-0.5 text-xs text-ink-2">{data.predictions.discount_response}</dd>
                  </div>
                  <div className="rounded-xl border border-line p-3">
                    <dt className="text-xs font-semibold">Price increase response</dt>
                    <dd className="mt-0.5 text-xs text-ink-2">{data.predictions.price_increase_response}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-[11px] italic text-muted">{data.predictions.label}</p>
              </Card>
            )}
          </div>
        )}

        <Card>
          <CardTitle className="mb-2">Behaviour Insights</CardTitle>
          <div className="grid gap-3 text-sm text-ink-2 md:grid-cols-3">
            <div className="rounded-xl bg-brand-soft/60 p-3.5">
              <p className="font-semibold text-ink">Loyalty is your engine</p>
              <p className="mt-1 text-xs leading-relaxed">{s.retention_pct}% of monthly visits come from returning customers — protect this with consistent stock on fast movers.</p>
            </div>
            <div className="rounded-xl bg-brand-soft/60 p-3.5">
              <p className="font-semibold text-ink">Each customer is worth {inr(s.clv)}</p>
              <p className="mt-1 text-xs leading-relaxed">Over a 12-month horizon at the current average ticket of {inr(s.avg_ticket)}. Losing one loyal customer costs far more than a discount.</p>
            </div>
            <div className="rounded-xl bg-brand-soft/60 p-3.5">
              <p className="font-semibold text-ink">Weekend peaks</p>
              <p className="mt-1 text-xs leading-relaxed">Footfall runs 25–30% above weekday average on Sat–Sun. Staff accordingly — simulate an extra weekend hire in the Simulator.</p>
            </div>
          </div>
        </Card>
      </motion.div>
    </AppShell>
  );
}
