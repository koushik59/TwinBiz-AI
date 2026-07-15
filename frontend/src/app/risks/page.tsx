"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, EmptyState, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

type Risk = { kind: string; severity: "critical" | "high" | "medium" | "low"; title: string; detail: string; confidence_pct?: number };

const sevRank = { critical: 0, high: 1, medium: 2, low: 3 };
const sevBar: Record<string, string> = {
  critical: "border-l-[var(--status-critical)]",
  high: "border-l-[var(--status-serious)]",
  medium: "border-l-[var(--status-warning)]",
  low: "border-l-[var(--status-good)]",
};

export default function RisksPage() {
  const [risks, setRisks] = useState<Risk[] | null>(null);

  useEffect(() => {
    api.get<{ risks: Risk[] }>("/api/insights/risks").then((d) => setRisks(d.risks)).catch(() => {});
  }, []);

  if (!risks) {
    return (
      <AppShell title="Risk Analyzer"><PageSkeleton /></AppShell>
    );
  }

  const counts = { critical: 0, high: 0, medium: 0, low: 0 } as Record<string, number>;
  risks.forEach((r) => counts[r.severity]++);

  return (
    <AppShell title="Risk Analyzer">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {(["critical", "high", "medium", "low"] as const).map((sev) => (
            <Card key={sev} className="text-center">
              <p className="text-3xl font-bold tabular-nums">{counts[sev]}</p>
              <Badge tone={sev} className="mt-2">{sev}</Badge>
            </Card>
          ))}
        </div>

        {risks.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No risks detected" hint="Your twin scanned finance, inventory, customers and operations — everything is within healthy bands." />
        ) : (
          <div className="space-y-3">
            {[...risks].sort((a, b) => sevRank[a.severity] - sevRank[b.severity]).map((r, i) => (
              <motion.div key={r.kind + i} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
                <Card className={cn("border-l-4", sevBar[r.severity])}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex items-start gap-3">
                      <AlertTriangle size={17} className={cn("mt-0.5 shrink-0", r.severity === "critical" ? "text-critical" : r.severity === "high" ? "text-serious" : r.severity === "medium" ? "text-warning" : "text-good")} />
                      <div>
                        <p className="font-semibold">{r.title}</p>
                        <p className="mt-1 text-sm leading-relaxed text-ink-2">{r.detail}</p>
                      </div>
                    </div>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      <Badge tone={r.severity}>{r.severity}</Badge>
                      {r.confidence_pct !== undefined && <span className="text-[10px] text-muted">confidence {r.confidence_pct}%</span>}
                    </span>
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    </AppShell>
  );
}
