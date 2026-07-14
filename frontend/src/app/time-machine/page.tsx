"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, PageSkeleton, StatTile } from "@/components/ui";
import { TrendArea } from "@/components/charts";
import { api } from "@/lib/api";
import { cn, inr, num, shortDate } from "@/lib/utils";
import { motion } from "framer-motion";
import { AlertTriangle, Calendar, History, Newspaper, PartyPopper, TrendingDown, TrendingUp, Users, Wallet } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type Replay = {
  available: boolean;
  date: string; weekday: string; festival: string | null;
  range: { min: string; max: string };
  day: { revenue: number; expenses: number; customers: number; orders: number; inventory_value: number } | null;
  kpis30: { revenue: number; expenses: number; profit: number; customers: number; revenue_change_pct: number; expense_change_pct: number; customer_change_pct: number };
  trend: { day: string; revenue: number; expenses: number; customers: number }[];
  cash_curve: { day: string; net: number; cumulative: number }[];
  top_products: { name: string; units: number; revenue: number }[];
  events: { day: string; kind: string; tone: string; title: string; detail: string }[];
  stock_snapshot: { products: { name: string; stock: number; daily_demand: number }[] } | null;
  note: string;
};
type News = {
  headlines: { date: string; dateline: string; tone: string; headline: string; story: string; based_on: string }[];
  label: string;
};

const dayMs = 86400000;

export default function TimeMachinePage() {
  const [replay, setReplay] = useState<Replay | null>(null);
  const [news, setNews] = useState<News | null>(null);
  const [offset, setOffset] = useState(0); // days back from the latest date
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = (dateStr?: string) => {
    setBusy(true);
    api.get<Replay>(`/api/intel/time-machine${dateStr ? `?date=${dateStr}` : ""}`)
      .then(setReplay).catch(() => {}).finally(() => setBusy(false));
  };

  useEffect(() => {
    load();
    api.get<News>("/api/intel/future-news").then(setNews).catch(() => {});
  }, []);

  if (!replay) return <AppShell title="Business Time Machine"><PageSkeleton /></AppShell>;
  if (!replay.available) {
    return (
      <AppShell title="Business Time Machine">
        <Card><p className="text-sm text-muted">{(replay as unknown as { note: string }).note}</p></Card>
      </AppShell>
    );
  }

  const maxDate = new Date(replay.range.max);
  const minDate = new Date(replay.range.min);
  const totalDays = Math.max(Math.round((maxDate.getTime() - minDate.getTime()) / dayMs), 1);

  const onSlide = (backDays: number) => {
    setOffset(backDays);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const d = new Date(maxDate.getTime() - backDays * dayMs);
      load(d.toISOString().slice(0, 10));
    }, 250);
  };

  const k = replay.kpis30;

  return (
    <AppShell title="Business Time Machine">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        {/* time slider */}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-1.5"><History size={14} className="text-brand" /> Travel to any recorded day</CardTitle>
            <div className="flex items-center gap-2 text-sm">
              <Calendar size={14} className="text-brand" />
              <span className={cn("font-semibold", busy && "opacity-50")}>{replay.weekday}, {shortDate(replay.date)}</span>
              {replay.festival && <Badge tone="brand"><PartyPopper size={11} /> {replay.festival}</Badge>}
              {offset === 0 && <Badge tone="good">Today</Badge>}
            </div>
          </div>
          <input
            type="range" min={0} max={totalDays} step={1} value={totalDays - offset}
            onChange={(e) => onSlide(totalDays - Number(e.target.value))}
            className="mt-4 w-full accent-[var(--brand)] cursor-pointer"
            aria-label="Replay date"
          />
          <div className="mt-1 flex justify-between text-[11px] text-muted">
            <span>{shortDate(replay.range.min)}</span>
            <div className="flex gap-2">
              {[90, 30, 7, 0].map((d) => (
                <button key={d} onClick={() => onSlide(d)}
                  className={cn("rounded-full border border-line px-2 py-0.5 transition-colors cursor-pointer",
                    offset === d ? "bg-brand-soft text-brand" : "hover:text-ink")}>
                  {d === 0 ? "Today" : `-${d}d`}
                </button>
              ))}
            </div>
            <span>{shortDate(replay.range.max)}</span>
          </div>
        </Card>

        {/* replayed state */}
        <div className={cn("space-y-5 transition-opacity", busy && "opacity-50")}>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatTile label="Revenue (trailing 30d)" value={inr(k.revenue)} delta={k.revenue_change_pct} icon={Wallet} />
            <StatTile label="Profit (trailing 30d)" value={inr(k.profit)} icon={TrendingUp} />
            <StatTile label="Expenses (trailing 30d)" value={inr(k.expenses)} delta={k.expense_change_pct} icon={TrendingDown} deltaGoodWhenDown />
            <StatTile label="Customers (trailing 30d)" value={num(k.customers)} delta={k.customer_change_pct} icon={Users} />
          </div>

          {replay.day && (
            <Card>
              <CardTitle className="mb-2">That day exactly</CardTitle>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-2">
                <span>Revenue <strong className="text-ink">{inr(replay.day.revenue)}</strong></span>
                <span>Expenses <strong className="text-ink">{inr(replay.day.expenses)}</strong></span>
                <span>Customers <strong className="text-ink">{num(replay.day.customers)}</strong></span>
                <span>Orders <strong className="text-ink">{num(replay.day.orders)}</strong></span>
                <span>Inventory value <strong className="text-ink">{inr(replay.day.inventory_value)}</strong></span>
              </div>
            </Card>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardTitle className="mb-3">60 days leading up to this date</CardTitle>
              <TrendArea data={replay.trend} x="day"
                series={[{ key: "revenue", label: "Revenue" }, { key: "expenses", label: "Expenses" }]} height={220} />
            </Card>
            <Card>
              <CardTitle className="mb-3">Cumulative cash flow (trailing 60d)</CardTitle>
              <TrendArea data={replay.cash_curve} x="day"
                series={[{ key: "cumulative", label: "Cumulative net" }]} height={220} />
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardTitle className="mb-3">What the AI found in this window</CardTitle>
              {replay.events.length === 0 ? (
                <p className="text-sm text-muted">A quiet month — no significant anomalies vs the weekday-typical baseline.</p>
              ) : (
                <div className="space-y-2.5">
                  {replay.events.map((e, i) => (
                    <div key={i} className="flex items-start gap-2.5 rounded-xl border border-line p-3">
                      <span className={cn("mt-0.5", e.tone === "good" ? "text-[var(--delta-good)]" : "text-critical")}>
                        {e.kind === "stockout" ? <AlertTriangle size={15} /> : e.tone === "good" ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                      </span>
                      <div>
                        <p className="text-sm font-semibold">{e.title} <span className="font-normal text-muted">· {shortDate(e.day)}</span></p>
                        <p className="mt-0.5 text-xs leading-relaxed text-ink-2">{e.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
            <Card>
              <CardTitle className="mb-3">Top sellers in the 14 days before</CardTitle>
              {replay.top_products.length === 0 ? (
                <p className="text-sm text-muted">Per-product sales history doesn&apos;t reach back this far.</p>
              ) : (
                <div className="space-y-1.5">
                  {replay.top_products.map((p) => (
                    <div key={p.name} className="flex items-center justify-between border-b border-line pb-1.5 text-sm last:border-0">
                      <span>{p.name}</span>
                      <span className="text-ink-2">{num(p.units)} units · <strong className="text-ink">{inr(p.revenue)}</strong></span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
          <p className="text-[11px] text-muted">{replay.note}</p>
        </div>

        {/* future news */}
        {news && news.headlines.length > 0 && (
          <Card>
            <CardTitle className="mb-1 flex items-center gap-1.5"><Newspaper size={14} className="text-brand" /> …and forward: tomorrow&apos;s headlines</CardTitle>
            <p className="mb-4 text-[11px] text-muted">{news.label}</p>
            <div className="grid gap-3 md:grid-cols-2">
              {news.headlines.map((h, i) => (
                <div key={i} className={cn("rounded-xl border p-4",
                  h.tone === "good" ? "border-[var(--delta-good)]/40" : h.tone === "bad" ? "border-critical/40" : "border-line")}>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted">{h.dateline} · TwinBiz Times</p>
                  <p className="mt-1 font-serif text-base font-bold leading-snug">{h.headline}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-ink-2">{h.story}</p>
                  <p className="mt-2 text-[10px] text-muted">Based on: {h.based_on}</p>
                </div>
              ))}
            </div>
          </Card>
        )}
      </motion.div>
    </AppShell>
  );
}
