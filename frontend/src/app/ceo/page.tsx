"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, EmptyState, PageSkeleton, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, shortDate } from "@/lib/utils";
import { motion } from "framer-motion";
import { Bot, Check, Crown, IndianRupee, Megaphone, PackagePlus, PiggyBank, Tags, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Decision = {
  id: string; kind: string; title: string; detail: string;
  expected_impact: string; impact_inr: number; action_type: string;
  status: "pending" | "approved" | "rejected"; result_note: string;
  created_at: string; decided_at: string | null;
};
type Inbox = { decisions: Decision[]; pending_count: number; pending_impact_inr: number; note: string };

const KIND_ICON = { restock: PackagePlus, price: IndianRupee, clearance: Tags, marketing: Megaphone, spending: PiggyBank } as const;

export default function CeoPage() {
  const { toast } = useToast();
  const [data, setData] = useState<Inbox | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [tab, setTab] = useState<"pending" | "history">("pending");

  const load = useCallback(() => {
    api.get<Inbox>("/api/intel/decisions").then(setData).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const decide = async (id: string, approve: boolean) => {
    setBusy(id);
    try {
      const r = await api.post<{ result_note: string }>(`/api/intel/decisions/${id}/${approve ? "approve" : "reject"}`);
      toast(r.result_note, approve ? "good" : "brand");
      load();
    } catch {
      toast("Could not record the decision", "critical");
    }
    setBusy(null);
  };

  if (!data) return <AppShell title="AI CEO Mode"><PageSkeleton /></AppShell>;

  const shown = data.decisions.filter((d) => (tab === "pending" ? d.status === "pending" : d.status !== "pending"));

  return (
    <AppShell title="AI CEO Mode">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Card className="flex items-center gap-3 px-4 py-3">
            <div className="rounded-xl bg-gradient-to-br from-brand to-brand-2 p-2 text-white"><Crown size={16} /></div>
            <div>
              <p className="text-lg font-bold leading-none">{data.pending_count}</p>
              <p className="text-[11px] text-muted">decisions awaiting you</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 px-4 py-3">
            <Bot size={18} className="text-brand" />
            <div>
              <p className="text-lg font-bold leading-none">{inr(data.pending_impact_inr)}</p>
              <p className="text-[11px] text-muted">simulated monthly impact on the table</p>
            </div>
          </Card>
          <p className="max-w-md text-xs leading-relaxed text-muted">{data.note}</p>
          <div className="ml-auto flex gap-1 rounded-xl border border-line p-1">
            {(["pending", "history"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={cn("rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors cursor-pointer",
                  tab === t ? "bg-brand-soft text-brand" : "text-muted hover:text-ink")}>
                {t}
              </button>
            ))}
          </div>
        </div>

        {shown.length === 0 ? (
          <EmptyState icon={Crown}
            title={tab === "pending" ? "Inbox zero — the AI has nothing urgent for you" : "No decided items yet"}
            hint={tab === "pending" ? "New proposals appear automatically as the twin detects restock needs, pricing headroom or cash pressure." : undefined} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {shown.map((d, i) => {
              const Icon = KIND_ICON[d.kind as keyof typeof KIND_ICON] ?? Bot;
              return (
                <motion.div key={d.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                  <Card className="flex h-full flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="rounded-xl bg-brand-soft p-2 text-brand"><Icon size={16} /></div>
                        <p className="font-semibold leading-snug">{d.title}</p>
                      </div>
                      <Badge tone={d.status === "approved" ? "good" : d.status === "rejected" ? "critical" : "brand"}>
                        {d.status}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm leading-relaxed text-ink-2">{d.detail}</p>
                    <p className="mt-2 text-sm font-semibold text-[var(--delta-good)]">{d.expected_impact}</p>
                    {d.result_note && d.status !== "pending" && (
                      <p className="mt-2 rounded-xl bg-brand-soft/50 p-2.5 text-xs text-ink-2">{d.result_note}</p>
                    )}
                    <div className="mt-auto flex items-center justify-between pt-4">
                      <p className="text-[11px] text-muted">
                        proposed {shortDate(d.created_at)}
                        {d.decided_at && ` · decided ${shortDate(d.decided_at)}`}
                      </p>
                      {d.status === "pending" && (
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" disabled={busy === d.id} onClick={() => decide(d.id, false)}>
                            <X size={13} /> Reject
                          </Button>
                          <Button size="sm" disabled={busy === d.id} onClick={() => decide(d.id, true)}>
                            <Check size={13} /> Approve
                          </Button>
                        </div>
                      )}
                    </div>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>
    </AppShell>
  );
}
