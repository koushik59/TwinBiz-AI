"use client";

import { Donut, TrendLines } from "@/components/charts";
import { AppShell } from "@/components/shell";
import { Card, CardTitle, PageSkeleton, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { inr } from "@/lib/utils";
import { motion } from "framer-motion";
import { Percent, PiggyBank, Target, Wallet } from "lucide-react";
import { useEffect, useState } from "react";

type Finance = {
  monthly: { month: string; revenue: number; expenses: number; profit: number; margin_pct: number }[];
  breakdown: { name: string; value: number }[];
  cash_flow: { day: string; net: number; cumulative: number }[];
  summary: {
    revenue: number; expenses: number; profit: number; margin_pct: number;
    roi_pct: number; breakeven_revenue: number; breakeven_reached: boolean;
  };
};

export default function FinancePage() {
  const [data, setData] = useState<Finance | null>(null);

  useEffect(() => {
    api.get<Finance>("/api/analytics/finance").then(setData).catch(() => {});
  }, []);

  if (!data) {
    return (
      <AppShell title="Financial Analytics"><PageSkeleton /></AppShell>
    );
  }

  const s = data.summary;

  return (
    <AppShell title="Financial Analytics">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatTile label="Revenue (30d)" value={inr(s.revenue)} icon={Wallet} />
          <StatTile label="Profit (30d)" value={inr(s.profit)} icon={PiggyBank} hint={`${s.margin_pct}% net margin`} />
          <StatTile label="ROI on Expenses" value={`${s.roi_pct}%`} icon={Percent} />
          <StatTile
            label="Break-even Revenue"
            value={inr(s.breakeven_revenue)}
            icon={Target}
            hint={s.breakeven_reached ? "✅ Above break-even" : "⚠️ Below break-even"}
          />
        </div>

        <Card>
          <CardTitle className="mb-3">Monthly Revenue · Expenses · Profit (12 months)</CardTitle>
          <TrendLines
            data={data.monthly}
            x="month"
            xIsDate={false}
            series={[
              { key: "revenue", label: "Revenue" },
              { key: "expenses", label: "Expenses" },
              { key: "profit", label: "Profit" },
            ]}
            height={300}
          />
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardTitle className="mb-3">Expense Breakdown (30d)</CardTitle>
            <Donut data={data.breakdown} height={260} />
          </Card>
          <Card>
            <CardTitle className="mb-3">Cumulative Cash Flow (30d)</CardTitle>
            <TrendLines data={data.cash_flow} x="day" series={[{ key: "cumulative", label: "Cumulative net cash" }]} height={260} />
          </Card>
        </div>

        <Card className="overflow-x-auto p-0">
          <div className="p-4 pb-2"><CardTitle>Month-by-Month Comparison</CardTitle></div>
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="px-4 py-2.5 font-semibold">Month</th>
                <th className="px-4 py-2.5 text-right font-semibold">Revenue</th>
                <th className="px-4 py-2.5 text-right font-semibold">Expenses</th>
                <th className="px-4 py-2.5 text-right font-semibold">Profit</th>
                <th className="px-4 py-2.5 text-right font-semibold">Margin</th>
              </tr>
            </thead>
            <tbody>
              {[...data.monthly].reverse().map((m) => (
                <tr key={m.month} className="border-b border-line last:border-0 transition-colors hover:bg-brand-soft/30">
                  <td className="px-4 py-3 font-medium">{m.month}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{inr(m.revenue)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{inr(m.expenses)}</td>
                  <td className={`px-4 py-3 text-right font-semibold tabular-nums ${m.profit >= 0 ? "text-[var(--delta-good)]" : "text-critical"}`}>{inr(m.profit)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{m.margin_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </motion.div>
    </AppShell>
  );
}
