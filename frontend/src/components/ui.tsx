"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { createContext, ReactNode, useCallback, useContext, useState } from "react";

/* ---------------------------------- Card --------------------------------- */

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("glass rounded-2xl p-5 shadow-sm", className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children }: { className?: string; children: ReactNode }) {
  return <h3 className={cn("text-sm font-medium text-ink-2", className)}>{children}</h3>;
}

/* --------------------------------- Button -------------------------------- */

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline" | "danger";
  size?: "sm" | "md" | "lg";
};

export function Button({ className, variant = "primary", size = "md", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all",
        "focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50 disabled:pointer-events-none",
        "active:scale-[0.98] cursor-pointer",
        variant === "primary" &&
          "bg-gradient-to-r from-brand to-brand-2 text-white shadow-md shadow-brand/25 hover:shadow-lg hover:shadow-brand/30 hover:brightness-110",
        variant === "ghost" && "text-ink-2 hover:bg-brand-soft hover:text-ink",
        variant === "outline" && "border border-line text-ink hover:bg-brand-soft",
        variant === "danger" && "bg-critical text-white hover:brightness-110",
        size === "sm" && "h-8 px-3 text-xs",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-12 px-6 text-base",
        className
      )}
      {...props}
    />
  );
}

/* --------------------------------- Inputs -------------------------------- */

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-xl border border-line bg-surface px-3 text-sm text-ink",
        "placeholder:text-muted focus:outline-2 focus:outline-brand/60 transition-shadow",
        className
      )}
      {...props}
    />
  );
}

export function Label({ className, children }: { className?: string; children: ReactNode }) {
  return <label className={cn("mb-1.5 block text-xs font-medium text-ink-2", className)}>{children}</label>;
}

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-10 w-full rounded-xl border border-line bg-surface px-3 text-sm text-ink",
        "focus:outline-2 focus:outline-brand/60 cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

/* --------------------------------- Badge --------------------------------- */

const severityStyles: Record<string, string> = {
  critical: "bg-critical/12 text-critical border-critical/30",
  high: "bg-serious/12 text-serious border-serious/30",
  serious: "bg-serious/12 text-serious border-serious/30",
  medium: "bg-warning/12 text-warning border-warning/30",
  low: "bg-good/12 text-good border-good/30",
  good: "bg-good/12 text-good border-good/30",
  healthy: "bg-good/12 text-good border-good/30",
  overstock: "bg-warning/12 text-warning border-warning/30",
  brand: "bg-brand-soft text-brand border-brand/30",
};

export function Badge({ tone = "brand", children, className }: { tone?: string; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        severityStyles[tone] ?? severityStyles.brand,
        className
      )}
    >
      {children}
    </span>
  );
}

/* -------------------------------- StatTile ------------------------------- */

export function StatTile({
  label,
  value,
  delta,
  icon: Icon,
  hint,
  deltaGoodWhenDown = false,
}: {
  label: string;
  value: string;
  delta?: number;
  icon?: LucideIcon;
  hint?: string;
  deltaGoodWhenDown?: boolean;
}) {
  const good = delta !== undefined && (deltaGoodWhenDown ? delta <= 0 : delta >= 0);
  return (
    <Card className="relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted">{label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</p>
        </div>
        {Icon && (
          <div className="rounded-xl bg-brand-soft p-2.5 text-brand">
            <Icon size={18} strokeWidth={2} />
          </div>
        )}
      </div>
      {delta !== undefined && (
        <p className={cn("mt-2 flex items-center gap-1 text-xs font-medium", good ? "text-[var(--delta-good)]" : "text-critical")}>
          {delta >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          {delta > 0 ? "+" : ""}
          {delta.toFixed(1)}%<span className="font-normal text-muted"> vs last month</span>
        </p>
      )}
      {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
    </Card>
  );
}

/* --------------------------------- Gauge --------------------------------- */

export function Gauge({ value, size = 120, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 14) / 2;
  const c = 2 * Math.PI * r;
  const tone = value >= 70 ? "var(--status-good)" : value >= 45 ? "var(--status-warning)" : "var(--status-critical)";
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--grid)" strokeWidth={9} />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={tone}
            strokeWidth={9}
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: c * (1 - value / 100) }}
            transition={{ duration: 1.1, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-semibold">{Math.round(value)}</span>
        </div>
      </div>
      {label && <p className="text-xs font-medium text-ink-2">{label}</p>}
    </div>
  );
}

/* -------------------------------- Skeleton ------------------------------- */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4 p-1">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}

/* --------------------------------- Slider -------------------------------- */

export function Slider({
  label,
  value,
  min,
  max,
  step = 1,
  unit = "%",
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
}) {
  const fracHere = (value - min) / (max - min);
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs font-medium text-ink-2">{label}</span>
        <span className={cn("rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums", value === 0 ? "text-muted" : "bg-brand-soft text-brand")}>
          {value > 0 && unit === "%" ? "+" : ""}
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-full accent-[var(--brand)]"
        style={{
          background: `linear-gradient(to right, var(--brand) ${fracHere * 100}%, var(--grid) ${fracHere * 100}%)`,
        }}
      />
    </div>
  );
}

/* ------------------------------- EmptyState ------------------------------ */

export function EmptyState({ icon: Icon, title, hint, action }: { icon: LucideIcon; title: string; hint?: string; action?: ReactNode }) {
  return (
    <Card className="flex flex-col items-center justify-center py-14 text-center">
      <div className="rounded-2xl bg-brand-soft p-4 text-brand">
        <Icon size={26} />
      </div>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-xs text-muted">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

/* ---------------------------------- Modal --------------------------------- */

export function Modal({
  open,
  onClose,
  title,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto p-4 pt-10 md:pt-16">
      <div className="fixed inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className={cn(
          "relative w-full rounded-2xl border border-line bg-surface p-5 shadow-2xl",
          wide ? "max-w-3xl" : "max-w-lg"
        )}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-muted hover:bg-brand-soft hover:text-ink cursor-pointer">
            ✕
          </button>
        </div>
        {children}
      </motion.div>
    </div>
  );
}

/* ---------------------------------- Toast --------------------------------- */


type Toast = { id: number; message: string; tone: "good" | "critical" | "brand" };
const ToastCtx = createContext<{ toast: (msg: string, tone?: Toast["tone"]) => void }>({ toast: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toast = useCallback((message: string, tone: Toast["tone"] = "brand") => {
    const id = Date.now();
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);
  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[100] flex flex-col gap-2">
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className={cn(
              "glass rounded-xl px-4 py-3 text-sm font-medium shadow-lg",
              t.tone === "good" && "border-good/40 text-good",
              t.tone === "critical" && "border-critical/40 text-critical"
            )}
          >
            {t.message}
          </motion.div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
