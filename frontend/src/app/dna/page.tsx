"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { Dna, Frown, Smile, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useState } from "react";

type Trait = { key: string; title: string; label: string; score: number; evidence: string };
type Mood = { mood: string; emoji: string; health: number; positives: string[]; negatives: string[] };
type DnaResult = { traits: Trait[]; mood: Mood; history_days: number; label: string };

function scoreTone(score: number) {
  if (score >= 70) return "var(--delta-good)";
  if (score >= 45) return "var(--warning, #eab308)";
  return "var(--critical, #ef4444)";
}

export default function DnaPage() {
  const [data, setData] = useState<DnaResult | null>(null);

  useEffect(() => {
    api.get<DnaResult>("/api/intel/dna").then(setData).catch(() => {});
  }, []);

  if (!data) return <AppShell title="Business DNA"><PageSkeleton /></AppShell>;
  const m = data.mood;

  return (
    <AppShell title="Business DNA">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        {/* mood banner */}
        <Card className="flex flex-wrap items-center gap-5">
          <div className="flex items-center gap-4">
            <span className="text-5xl">{m.emoji}</span>
            <div>
              <p className="text-lg font-bold">Your business feels <span className="gradient-text">{m.mood}</span></p>
              <p className="text-xs text-muted">Overall health {m.health}/100 · measured from {data.history_days} days of history</p>
            </div>
          </div>
          <div className="ml-auto grid gap-4 text-xs sm:grid-cols-2">
            <div>
              {m.positives.map((p, i) => (
                <p key={i} className="flex items-start gap-1.5 text-ink-2">
                  <ThumbsUp size={12} className="mt-0.5 shrink-0 text-[var(--delta-good)]" /> {p}
                </p>
              ))}
            </div>
            <div>
              {m.negatives.length === 0 ? (
                <p className="flex items-center gap-1.5 text-muted"><Smile size={12} /> Nothing weighing it down</p>
              ) : m.negatives.map((n, i) => (
                <p key={i} className="flex items-start gap-1.5 text-ink-2">
                  <ThumbsDown size={12} className="mt-0.5 shrink-0 text-critical" /> {n}
                </p>
              ))}
            </div>
          </div>
        </Card>

        {/* traits */}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.traits.map((t, i) => (
            <motion.div key={t.key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
              <Card className="h-full">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-1.5"><Dna size={13} className="text-brand" /> {t.title}</CardTitle>
                  <Badge tone={t.score >= 70 ? "good" : t.score >= 45 ? "medium" : "critical"}>{t.label}</Badge>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-grid">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${t.score}%` }} transition={{ duration: 0.7, delay: i * 0.06 }}
                    className="h-full rounded-full" style={{ background: scoreTone(t.score) }} />
                </div>
                <p className="mt-1 text-right text-[11px] font-semibold" style={{ color: scoreTone(t.score) }}>{t.score}/100</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-2">{t.evidence}</p>
              </Card>
            </motion.div>
          ))}
        </div>

        <p className="text-[11px] text-muted">{data.label}</p>
      </motion.div>
    </AppShell>
  );
}
