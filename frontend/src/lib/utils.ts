import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** ₹ compact: 1,23,456 → ₹1.23L ; 1.5M → ₹15L style Indian units */
export function inr(n: number | undefined | null, compact = true): string {
  if (n === undefined || n === null || isNaN(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (!compact) return `${sign}₹${abs.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(1)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
}

export function num(n: number | undefined | null): string {
  if (n === undefined || n === null || isNaN(n)) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function pct(n: number | undefined | null, signed = true): string {
  if (n === undefined || n === null || isNaN(n)) return "—";
  return `${signed && n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export function shortDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
