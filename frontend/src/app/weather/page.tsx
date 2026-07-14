"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, shortDate } from "@/lib/utils";
import { motion } from "framer-motion";
import { Boxes, CloudSun, Wallet, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

type Layer = { sky: string; icon: string; note: string };
type Day = {
  day: string; weekday: string; overall: string; overall_icon: string;
  sales: Layer; inventory: Layer; cash: Layer;
};
type Weather = { days: Day[]; model_confidence_pct?: number; note: string };

const SKY_LABEL: Record<string, string> = {
  sunny: "Clear", partly: "Fair", cloudy: "Watch", storm: "Storm",
};
const SKY_EMOJI: Record<string, string> = {
  sunny: "☀️", partly: "🌤️", cloudy: "☁️", storm: "⛈️",
};

export default function WeatherPage() {
  const [data, setData] = useState<Weather | null>(null);
  const [horizon, setHorizon] = useState(7);

  useEffect(() => {
    setData(null);
    api.get<Weather>(`/api/intel/weather?days=${horizon}`).then(setData).catch(() => {});
  }, [horizon]);

  if (!data) return <AppShell title="Business Weather"><PageSkeleton /></AppShell>;

  return (
    <AppShell title="Business Weather">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-xl text-sm text-ink-2">
            Your next {horizon} business days as a weather report — sales from the ML forecast,
            inventory from live stock velocity, cash from projected daily net.
          </p>
          <div className="flex items-center gap-2">
            {data.model_confidence_pct !== undefined && (
              <Badge tone="brand">Model confidence {data.model_confidence_pct}%</Badge>
            )}
            <div className="flex gap-1 rounded-xl border border-line p-1">
              {[7, 14].map((h) => (
                <button key={h} onClick={() => setHorizon(h)}
                  className={cn("rounded-lg px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                    horizon === h ? "bg-brand-soft text-brand" : "text-muted hover:text-ink")}>
                  {h} days
                </button>
              ))}
            </div>
          </div>
        </div>

        {data.days.length === 0 ? (
          <Card><p className="text-sm text-muted">{data.note}</p></Card>
        ) : (
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {data.days.map((d, i) => (
              <motion.div key={d.day} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <Card className={cn("h-full", d.overall === "storm" && "border-critical/50",
                  d.overall === "sunny" && "border-[var(--delta-good)]/40")}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold">{i === 0 ? "Today" : i === 1 ? "Tomorrow" : d.weekday}</p>
                      <p className="text-[11px] text-muted">{shortDate(d.day)}</p>
                    </div>
                    <span className="text-2xl" title={SKY_LABEL[d.overall]}>{SKY_EMOJI[d.overall]}</span>
                  </div>
                  <div className="mt-3 space-y-2 text-xs">
                    {([["Sales", d.sales, TrendingUp], ["Inventory", d.inventory, Boxes], ["Cash", d.cash, Wallet]] as const).map(([label, layer, Icon]) => (
                      <div key={label} className="flex items-start gap-2">
                        <Icon size={13} className="mt-0.5 shrink-0 text-muted" />
                        <div className="min-w-0">
                          <p className="font-medium">
                            {label} <span>{SKY_EMOJI[layer.sky]}</span>{" "}
                            <span className={cn("text-[10px] font-semibold uppercase tracking-wide",
                              layer.sky === "storm" ? "text-critical" : layer.sky === "cloudy" ? "text-warning" : "text-[var(--delta-good)]")}>
                              {SKY_LABEL[layer.sky]}
                            </span>
                          </p>
                          <p className="truncate text-[11px] text-muted" title={layer.note}>{layer.note}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        <p className="flex items-start gap-1.5 text-[11px] text-muted">
          <CloudSun size={13} className="mt-0.5 shrink-0" /> {data.note}
        </p>
      </motion.div>
    </AppShell>
  );
}
