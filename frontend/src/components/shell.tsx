"use client";

import { api, getToken, setToken } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  Boxes,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  LineChart,
  LogOut,
  Menu,
  Moon,
  Network,
  PiggyBank,
  Settings,
  Sparkles,
  Sun,
  Users,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  { group: "Overview", items: [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/twin", label: "Digital Twin", icon: Network },
  ]},
  { group: "Decision Lab", items: [
    { href: "/simulator", label: "Simulator", icon: FlaskConical },
    { href: "/scenarios", label: "Scenarios", icon: GitCompareArrows },
    { href: "/forecast", label: "Forecasting", icon: LineChart },
    { href: "/advisor", label: "AI Advisor", icon: Bot },
  ]},
  { group: "Intelligence", items: [
    { href: "/inventory", label: "Inventory", icon: Boxes },
    { href: "/finance", label: "Financials", icon: Wallet },
    { href: "/customers", label: "Customers", icon: Users },
    { href: "/risks", label: "Risk Analyzer", icon: AlertTriangle },
    { href: "/recommendations", label: "Recommendations", icon: Sparkles },
  ]},
  { group: "Operations", items: [
    { href: "/alerts", label: "Alert Center", icon: Bell },
    { href: "/reports", label: "Reports", icon: BarChart3 },
    { href: "/settings", label: "Settings", icon: Settings },
  ]},
];

export function useTheme() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const stored = localStorage.getItem("twinbiz_theme");
    const isDark = stored ? stored === "dark" : true;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("twinbiz_theme", next ? "dark" : "light");
  };
  return { dark, toggle };
}

export function ThemeToggle() {
  const { dark, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="rounded-xl border border-line p-2 text-ink-2 transition-colors hover:bg-brand-soft hover:text-ink cursor-pointer"
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-brand-2 text-white shadow-md shadow-brand/30">
        <Network size={16} />
      </div>
      {!compact && (
        <span className="text-base font-bold tracking-tight">
          TwinBiz <span className="gradient-text">AI</span>
        </span>
      )}
    </Link>
  );
}

export function AppShell({ children, title }: { children: React.ReactNode; title: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [alertCount, setAlertCount] = useState(0);
  const [businessName, setBusinessName] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    api.get<{ alerts: unknown[] }>("/api/insights/alerts").then((d) => setAlertCount(d.alerts.length)).catch(() => {});
    api
      .get<{ name: string }>("/api/business")
      .then((b) => setBusinessName(b.name))
      .catch((e) => {
        if (e instanceof Error && "status" in e && (e as { status: number }).status === 404) router.push("/setup");
      });
  }, [router]);

  const logout = () => {
    setToken(null);
    router.push("/login");
  };

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 py-5">
        <Logo />
        <button className="lg:hidden text-muted" onClick={() => setOpen(false)} aria-label="Close menu">
          <X size={18} />
        </button>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {NAV.map((group) => (
          <div key={group.group}>
            <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{group.group}</p>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium transition-all",
                      active
                        ? "bg-gradient-to-r from-brand/15 to-brand-2/10 text-brand shadow-sm"
                        : "text-ink-2 hover:bg-brand-soft hover:text-ink"
                    )}
                  >
                    <item.icon size={16} strokeWidth={active ? 2.2 : 1.8} />
                    {item.label}
                    {item.href === "/alerts" && alertCount > 0 && (
                      <span className="ml-auto rounded-full bg-critical/15 px-1.5 py-0.5 text-[10px] font-bold text-critical">{alertCount}</span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-line p-3">
        <button
          onClick={logout}
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium text-ink-2 transition-colors hover:bg-critical/10 hover:text-critical cursor-pointer"
        >
          <LogOut size={16} /> Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-bg">
      {/* desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-line bg-surface/70 backdrop-blur-xl lg:block">
        {sidebar}
      </aside>
      {/* mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-surface shadow-2xl">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-bg/80 px-4 backdrop-blur-xl lg:px-8">
          <button className="lg:hidden text-ink-2" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <h1 className="text-sm font-semibold tracking-tight">{title}</h1>
          {businessName && (
            <span className="hidden rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-2 sm:inline">
              {businessName}
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <Link href="/alerts" className="relative rounded-xl border border-line p-2 text-ink-2 transition-colors hover:bg-brand-soft" aria-label="Alerts">
              <Bell size={16} />
              {alertCount > 0 && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-critical ring-2 ring-[var(--bg)]" />}
            </Link>
            <ThemeToggle />
          </div>
        </header>
        <main className="flex-1 p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
