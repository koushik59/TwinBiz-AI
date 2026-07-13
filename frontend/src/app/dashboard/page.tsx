"use client";

import { Donut, SimpleBars, TrendArea, TrendLines } from "@/components/charts";
import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, Gauge, PageSkeleton, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, num, pct } from "@/lib/utils";
import { motion } from "framer-motion";
import { Activity, ArrowRight, Bot, Boxes, ShoppingCart, Sparkles, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

type Dashboard = {
  kpis: Record<string, number>;
  health: { overall: number; pillars: Record<string, number> };
  twin_status?: { status: string; data_source: string; last_sync: string | null; history_days: number; data_quality_pct: number; confidence_pct: number };
  trend: { day: string; revenue: number; expenses: number; profit: number; customers: number; orders: number }[];
  weekly_trend: { week: string; revenue: number; expenses: number; profit: number; customers: number }[];
  top_products: { name: string; units: number; revenue: number }[];
  peak_hours: { hour: string; customers: number }[];
};
type Risk = { severity: string; title: string; detail: string };
type Rec = { title: string; reason: string; priority: string; est_revenue_uplift: number };

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [recs, setRecs] = useState<Rec[]>([]);
  const [range, setRange] = useState<30 | 90>(30);

  useEffect(() => {
    api.get<Dashboard>("/api/analytics/dashboard").then(setData).catch(() => {});
    api.get<{ risks: Risk[] }>("/api/insights/risks").then((d) => setRisks(d.risks)).catch(() => {});
    api.get<{ recommendations: Rec[] }>("/api/insights/recommendations").then((d) => setRecs(d.recommendations)).catch(() => {});
  }, []);

  if (!data) {
    return (
      <AppShell title="Dashboard">
        <PageSkeleton />
      </AppShell>
    );
  }

  const k = data.kpis;
  const trend = data.trend.slice(-range);

  return (
    <AppShell title="Dashboard">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        {/* twin status strip */}
        {data.twin_status && (
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <Badge tone={data.twin_status.status === "LIVE" ? "good" : data.twin_status.status === "DEMO" ? "brand" : "critical"}>
              Twin: {data.twin_status.status}{data.twin_status.status === "DEMO" ? " DATA" : ""}
            </Badge>
            <span>Last sync {data.twin_status.last_sync ?? "—"}</span>
            <span>· {num(data.twin_status.history_days)} days of history</span>
            <span>· Data quality {data.twin_status.data_quality_pct}%</span>
            <span>· Twin confidence {data.twin_status.confidence_pct}%</span>
            {data.twin_status.status === "DEMO" && (
              <Link href="/data-center" className="font-medium text-brand hover:underline">Import real data →</Link>
            )}
          </div>
        )}
        {/* KPI row */}
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatTile label="Monthly Revenue" value={inr(k.monthly_revenue)} delta={k.revenue_change_pct} icon={Wallet} />
          <StatTile label="Monthly Profit" value={inr(k.monthly_profit)} delta={k.profit_change_pct} icon={Activity} hint={`${k.profit_margin_pct}% margin`} />
          <StatTile label="Expenses" value={inr(k.monthly_expenses)} delta={k.expense_change_pct} icon={ShoppingCart} deltaGoodWhenDown />
          <StatTile label="Customers" value={num(k.monthly_customers)} delta={k.customer_change_pct} icon={Users} />
        </div>
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatTile label="Today's Revenue" value={inr(k.today_revenue)} icon={Wallet} hint={`${num(k.today_orders)} orders today`} />
          <StatTile label="Today's Customers" value={num(k.today_customers)} icon={Users} />
          <StatTile label="Inventory Value" value={inr(k.inventory_value)} icon={Boxes} />
          <Card className="flex items-center justify-center">
            <Gauge value={data.health.overall} size={92} label="Business Health" />
          </Card>
        </div>

        {/* main trend */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <CardTitle>Revenue vs Expenses</CardTitle>
            <div className="flex gap-1 rounded-lg border border-line p-0.5">
              {([30, 90] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${range === r ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"}`}
                >
                  {r}d
                </button>
              ))}
            </div>
          </div>
          <TrendArea data={trend} x="day" series={[{ key: "revenue", label: "Revenue" }, { key: "expenses", label: "Expenses" }]} />
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardTitle className="mb-3">Profit Trend (weekly)</CardTitle>
            <TrendLines data={data.weekly_trend} x="week" series={[{ key: "profit", label: "Profit" }]} height={240} />
          </Card>
          <Card>
            <CardTitle className="mb-3">Customer Footfall</CardTitle>
            <TrendArea data={trend} x="day" series={[{ key: "customers", label: "Customers" }]} height={240} money={false} />
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-1">
            <CardTitle className="mb-3">Top Selling Products (30d)</CardTitle>
            <SimpleBars data={data.top_products} x="name" y="revenue" label="Revenue" horizontal height={260} />
          </Card>
          <Card>
            <CardTitle className="mb-3">Peak Business Hours</CardTitle>
            <SimpleBars data={data.peak_hours} x="hour" y="customers" label="Customers" money={false} height={260} />
          </Card>
          <Card>
            <CardTitle className="mb-3">Health Pillars</CardTitle>
            <div className="grid grid-cols-2 gap-y-4 pt-2">
              {Object.entries(data.health.pillars).map(([name, value]) => (
                <Gauge key={name} value={value} size={84} label={name[0].toUpperCase() + name.slice(1)} />
              ))}
            </div>
          </Card>
        </div>

        {/* risks + AI suggestions */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <CardTitle>Upcoming Risks</CardTitle>
              <Link href="/risks" className="flex items-center gap-1 text-xs font-medium text-brand hover:underline">
                Risk Analyzer <ArrowRight size={12} />
              </Link>
            </div>
            <div className="space-y-2.5">
              {risks.slice(0, 4).map((r) => (
                <div key={r.title} className="flex items-start gap-3 rounded-xl border border-line p-3">
                  <Badge tone={r.severity}>{r.severity}</Badge>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{r.title}</p>
                    <p className="mt-0.5 text-xs text-muted">{r.detail}</p>
                  </div>
                </div>
              ))}
              {risks.length === 0 && <p className="py-6 text-center text-sm text-muted">No risks detected — smooth sailing 🎉</p>}
            </div>
          </Card>
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <CardTitle className="flex items-center gap-1.5"><Sparkles size={14} className="text-brand" /> AI Suggestions</CardTitle>
              <Link href="/advisor" className="flex items-center gap-1 text-xs font-medium text-brand hover:underline">
                Ask Advisor <Bot size={12} />
              </Link>
            </div>
            <div className="space-y-2.5">
              {recs.slice(0, 3).map((r) => (
                <div key={r.title} className="rounded-xl bg-brand-soft/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{r.title}</p>
                    {r.est_revenue_uplift > 0 && <span className="shrink-0 text-xs font-semibold text-[var(--delta-good)]">{inr(r.est_revenue_uplift)}/mo</span>}
                  </div>
                  <p className="mt-0.5 text-xs text-ink-2">{r.reason}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </motion.div>
    </AppShell>
  );
}
