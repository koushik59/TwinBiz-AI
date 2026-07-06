"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { Bot, Send, Sparkles, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type Msg = { id: number; role: "user" | "assistant"; content: string; source?: string; confidence?: string };

const SUGGESTIONS = [
  "Why did sales decrease?",
  "Should I hire another employee?",
  "What happens if I increase price by 10%?",
  "Which products should I stock more?",
  "How can I improve my profit margin?",
];

/** minimal markdown: **bold**, *italic*, line breaks */
function renderMd(text: string) {
  const html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br/>");
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

export default function AdvisorPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(0);

  useEffect(() => {
    api.get<{ messages: Msg[] }>("/api/insights/advisor/history").then((d) => {
      const withIds = d.messages.map((m) => ({ ...m, id: nextId.current++ }));
      setMessages(withIds);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const ask = async (question: string) => {
    if (!question.trim() || thinking) return;
    setInput("");
    const userMsg: Msg = { id: nextId.current++, role: "user", content: question };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);
    try {
      const res = await api.post<{ answer: string; source: string; confidence: string }>("/api/insights/advisor", { message: question });
      setMessages((m) => [...m, { id: nextId.current++, role: "assistant", content: res.answer, source: res.source, confidence: res.confidence }]);
    } catch {
      setMessages((m) => [...m, { id: nextId.current++, role: "assistant", content: "Sorry — I couldn't reach the twin engine. Please try again." }]);
    }
    setThinking(false);
  };

  return (
    <AppShell title="AI Business Advisor">
      <div className="mx-auto flex h-[calc(100vh-8.5rem)] max-w-3xl flex-col">
        <Card className="flex min-h-0 flex-1 flex-col p-0">
          {/* messages */}
          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            {messages.length === 0 && !thinking && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="rounded-2xl bg-gradient-to-br from-brand to-brand-2 p-4 text-white shadow-lg shadow-brand/25">
                  <Bot size={28} />
                </div>
                <h2 className="mt-4 text-lg font-semibold">Ask your business anything</h2>
                <p className="mt-1 max-w-sm text-sm text-muted">
                  I&apos;m grounded in your live twin — your sales, inventory, risks and forecasts. Every answer includes a prediction, recommendation and confidence score.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => ask(s)} className="rounded-full border border-line px-3 py-1.5 text-xs text-ink-2 transition-all hover:border-brand/40 hover:bg-brand-soft hover:text-brand cursor-pointer">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}
              >
                <div className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
                  m.role === "user" ? "bg-surface border border-line text-ink-2" : "bg-gradient-to-br from-brand to-brand-2 text-white"
                )}>
                  {m.role === "user" ? <User size={15} /> : <Bot size={15} />}
                </div>
                <div className={cn(
                  "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  m.role === "user" ? "bg-gradient-to-r from-brand to-brand-2 text-white" : "border border-line bg-surface/70"
                )}>
                  {renderMd(m.content)}
                  {m.role === "assistant" && m.source && (
                    <div className="mt-2.5 flex gap-2">
                      <Badge tone="brand"><Sparkles size={10} /> {m.source === "gemini" ? "Gemini AI" : "Twin Engine"}</Badge>
                      {m.confidence && <Badge tone="low">Confidence: {m.confidence}</Badge>}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
            {thinking && (
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-brand-2 text-white"><Bot size={15} /></div>
                <div className="flex gap-1.5 rounded-2xl border border-line bg-surface/70 px-4 py-3.5">
                  {[0, 1, 2].map((i) => (
                    <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-brand" animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 1, delay: i * 0.2 }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* composer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
            className="flex gap-2 border-t border-line p-3"
          >
            <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="e.g. Should I launch a weekend discount?" />
            <Button type="submit" disabled={thinking || !input.trim()} aria-label="Send"><Send size={15} /></Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
