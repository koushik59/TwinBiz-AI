"use client";

import { ForecastChart } from "@/components/charts";
import { AppShell } from "@/components/shell";
import { Card, CardTitle, PageSkeleton, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { Brain, CalendarDays, CalendarRange, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

type Forecast = {
  forecast: { day: string; value: number; low: number; high: number }[];
  history: { day: string; value: number }[];
  confidence: number;
  trend_pct_per_month: number;
  summary: { next_day: number; next_week: number; next_month: number };
};

const METRICS = [
  { key: "revenue", label: "Revenue", money: true },
  { key: "customers", label: "Customers", money: false },
  { key: "orders", label: "Orders", money: false },
  { key: "expenses", label: "Expenses", money: true },
] as const;

export default function ForecastPage() {
  const [metric, setMetric] = useState<(typeof METRICS)[number]>(METRICS[0]);
  const [horizon, setHorizon] = useState(30);
  const [data, setData] = useState<Forecast | null>(null);

  useEffect(() => {
    setData(null);
    api.get<Forecast>(`/api/simulate/forecast?metric=${metric.key}&horizon=${horizon}`).then(setData).catch(() => {});
  }, [metric, horizon]);

  const fmt = metric.money ? inr : num;

  return (
    <AppShell title="Predictive Forecasting">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-xl border border-line p-1">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetric(m)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                metric.key === m.key ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 rounded-xl border border-line p-1">
          {[14, 30, 60, 90].map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                horizon === h ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"
              )}
            >
              {h}d
            </button>
          ))}
        </div>
      </div>

      {!data ? (
        <PageSkeleton />
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatTile label={`Next Day ${metric.label}`} value={fmt(data.summary.next_day)} icon={CalendarDays} />
            <StatTile label={`Next 7 Days`} value={fmt(data.summary.next_week)} icon={CalendarRange} />
            <StatTile label={`Next 30 Days`} value={fmt(data.summary.next_month)} icon={TrendingUp} />
            <StatTile label="Model Confidence" value={`${data.confidence}%`} icon={Brain} hint={`Trend: ${data.trend_pct_per_month > 0 ? "+" : ""}${data.trend_pct_per_month}%/month`} />
          </div>

          <Card>
            <CardTitle className="mb-1">{metric.label} — actuals & {horizon}-day ML forecast</CardTitle>
            <p className="mb-3 text-xs text-muted">
              Ridge regression with weekly seasonality trained on your twin&apos;s history. Shaded band = 80% confidence interval.
            </p>
            <ForecastChart history={data.history} forecast={data.forecast} money={metric.money} height={360} />
          </Card>

          <Card>
            <CardTitle className="mb-2">How to read this</CardTitle>
            <p className="text-sm leading-relaxed text-ink-2">
              The model learned your weekday rhythm (weekends run higher) and your growth trend
              ({data.trend_pct_per_month > 0 ? "+" : ""}{data.trend_pct_per_month}% per month). Expect roughly {fmt(data.summary.next_week)} in {metric.label.toLowerCase()} over
              the coming week. If actuals fall below the lower band for 3+ consecutive days, something changed — check the Risk Analyzer.
            </p>
          </Card>
        </motion.div>
      )}
    </AppShell>
  );
}
