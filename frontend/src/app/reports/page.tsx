"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, PageSkeleton } from "@/components/ui";
import { api, getToken, API_BASE } from "@/lib/api";
import { cn, inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { Download, FileText, Printer } from "lucide-react";
import { useEffect, useState } from "react";

type Report = {
  period: string;
  business: string;
  generated: string;
  summary: { revenue: number; expenses: number; profit: number; customers: number; orders: number; margin_pct: number };
  health: { overall: number; pillars: Record<string, number> };
  risks: { severity: string; title: string; detail: string }[];
  recommendations: { title: string; priority: string; est_revenue_uplift: number }[];
};

const PERIODS = [
  { key: "daily", label: "Daily" },
  { key: "weekly", label: "Weekly" },
  { key: "monthly", label: "Monthly" },
];

export default function ReportsPage() {
  const [period, setPeriod] = useState("monthly");
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    setReport(null);
    api.get<Report>(`/api/insights/report?period=${period}`).then(setReport).catch(() => {});
  }, [period]);

  const downloadCsv = async () => {
    const res = await fetch(`${API_BASE}/api/insights/report/csv?period=${period}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `twinbiz_${period}_report.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell title="Reports">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 rounded-xl border border-line p-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                period === p.key ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={downloadCsv}><Download size={14} /> Export CSV</Button>
          <Button variant="outline" size="sm" onClick={() => window.print()}><Printer size={14} /> Print / PDF</Button>
        </div>
      </div>

      {!report ? (
        <PageSkeleton />
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mx-auto max-w-3xl p-8 print:shadow-none">
            <div className="flex items-start justify-between border-b border-line pb-5">
              <div>
                <div className="flex items-center gap-2 text-brand">
                  <FileText size={18} />
                  <p className="text-xs font-bold uppercase tracking-widest">{report.period} performance report</p>
                </div>
                <h2 className="mt-2 text-2xl font-bold">{report.business}</h2>
                <p className="text-xs text-muted">Generated {report.generated} by TwinBiz AI</p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">{Math.round(report.health.overall)}<span className="text-base text-muted">/100</span></p>
                <p className="text-xs text-muted">Business health</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 border-b border-line py-5">
              {[
                ["Revenue", inr(report.summary.revenue)],
                ["Expenses", inr(report.summary.expenses)],
                ["Profit", inr(report.summary.profit)],
                ["Customers", num(report.summary.customers)],
                ["Orders", num(report.summary.orders)],
                ["Net margin", `${report.summary.margin_pct}%`],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-[11px] uppercase tracking-wide text-muted">{k}</p>
                  <p className="mt-0.5 text-lg font-semibold tabular-nums">{v}</p>
                </div>
              ))}
            </div>

            <div className="border-b border-line py-5">
              <CardTitle className="mb-3">Health pillars</CardTitle>
              <div className="space-y-2">
                {Object.entries(report.health.pillars).map(([name, value]) => (
                  <div key={name} className="flex items-center gap-3">
                    <span className="w-24 text-xs capitalize text-ink-2">{name}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-grid">
                      <div className="h-full rounded-full bg-gradient-to-r from-brand to-brand-2" style={{ width: `${value}%` }} />
                    </div>
                    <span className="w-8 text-right text-xs font-semibold tabular-nums">{Math.round(value)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-b border-line py-5">
              <CardTitle className="mb-3">Detected risks ({report.risks.length})</CardTitle>
              <div className="space-y-2">
                {report.risks.map((r) => (
                  <div key={r.title} className="flex items-start gap-2.5 text-sm">
                    <Badge tone={r.severity}>{r.severity}</Badge>
                    <div>
                      <p className="font-medium">{r.title}</p>
                      <p className="text-xs text-muted">{r.detail}</p>
                    </div>
                  </div>
                ))}
                {report.risks.length === 0 && <p className="text-sm text-muted">No risks detected in this period.</p>}
              </div>
            </div>

            <div className="pt-5">
              <CardTitle className="mb-3">Recommended actions</CardTitle>
              <ol className="space-y-2">
                {report.recommendations.map((r, i) => (
                  <li key={r.title} className="flex items-center gap-2.5 text-sm">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[11px] font-bold text-brand">{i + 1}</span>
                    <span className="font-medium">{r.title}</span>
                    {r.est_revenue_uplift > 0 && <span className="ml-auto text-xs font-semibold text-[var(--delta-good)]">≈ {inr(r.est_revenue_uplift)}/mo</span>}
                  </li>
                ))}
              </ol>
            </div>
          </Card>
        </motion.div>
      )}
    </AppShell>
  );
}
