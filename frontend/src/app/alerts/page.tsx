"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, EmptyState, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { AlertOctagon, AlertTriangle, Bell, BellOff, Info } from "lucide-react";
import { useEffect, useState } from "react";

type Alert = { severity: string; title: string; detail: string; kind: string; time: string };

const iconFor = (sev: string) =>
  sev === "critical" ? AlertOctagon : sev === "high" ? AlertTriangle : sev === "medium" ? Bell : Info;

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api.get<{ alerts: Alert[] }>("/api/insights/alerts").then((d) => setAlerts(d.alerts)).catch(() => {});
  }, []);

  if (!alerts) {
    return (
      <AppShell title="Alert Center"><PageSkeleton /></AppShell>
    );
  }

  const filtered = filter === "all" ? alerts : alerts.filter((a) => a.severity === filter);

  return (
    <AppShell title="Alert Center">
      <div className="mb-4 flex gap-1 rounded-xl border border-line p-1 w-fit">
        {["all", "critical", "high", "medium"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors cursor-pointer",
              filter === f ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"
            )}
          >
            {f} {f !== "all" && `(${alerts.filter((a) => a.severity === f).length})`}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={BellOff} title="No alerts" hint="Nothing needs your attention right now — the twin keeps watching 24/7." />
      ) : (
        <div className="space-y-3">
          {filtered.map((a, i) => {
            const Icon = iconFor(a.severity);
            return (
              <motion.div key={a.title + i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <Card
                  className={cn(
                    "flex items-start gap-3 border-l-4",
                    a.severity === "critical" && "border-l-[var(--status-critical)]",
                    a.severity === "high" && "border-l-[var(--status-serious)]",
                    a.severity === "medium" && "border-l-[var(--status-warning)]",
                    a.severity === "low" && "border-l-[var(--status-good)]"
                  )}
                >
                  <Icon
                    size={18}
                    className={cn(
                      "mt-0.5 shrink-0",
                      a.severity === "critical" ? "text-critical" : a.severity === "high" ? "text-serious" : a.severity === "medium" ? "text-warning" : "text-good"
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold">{a.title}</p>
                      <span className="text-[11px] text-muted">{a.time}</span>
                    </div>
                    <p className="mt-0.5 text-sm text-ink-2">{a.detail}</p>
                  </div>
                  <Badge tone={a.severity}>{a.severity}</Badge>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
