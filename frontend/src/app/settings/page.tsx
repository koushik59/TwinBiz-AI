"use client";

import { AppShell, useTheme } from "@/components/shell";
import { Button, Card, CardTitle, Input, Label, PageSkeleton, Select, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { Building2, KeyRound, Moon, Palette, Sun, User2 } from "lucide-react";
import { useEffect, useState } from "react";

type Business = {
  name: string; business_type: string; location: string; employees_count: number;
  monthly_revenue: number; monthly_expenses: number; customer_count: number; working_hours: string;
};
type Me = { full_name: string; email: string; role: string };

const TYPES = ["Supermarket", "Retail", "Restaurant", "Pharmacy", "Salon", "Bakery", "Warehouse", "Manufacturing", "Education"];

export default function SettingsPage() {
  const { toast } = useToast();
  const { dark, toggle } = useTheme();
  const [me, setMe] = useState<Me | null>(null);
  const [biz, setBiz] = useState<Business | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<Me>("/api/auth/me").then(setMe).catch(() => {});
    api.get<Business>("/api/business").then(setBiz).catch(() => {});
  }, []);

  const save = async () => {
    if (!biz) return;
    setSaving(true);
    try {
      await api.put("/api/business", biz);
      toast("Business details updated — twin recalibrated", "good");
    } catch {
      toast("Failed to save", "critical");
    }
    setSaving(false);
  };

  if (!me || !biz) {
    return (
      <AppShell title="Settings"><PageSkeleton /></AppShell>
    );
  }

  const set = (k: keyof Business, v: string | number) => setBiz((b) => (b ? { ...b, [k]: v } : b));

  return (
    <AppShell title="Settings">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-2xl space-y-5">
        <Card>
          <CardTitle className="mb-4 flex items-center gap-1.5"><User2 size={14} className="text-brand" /> Profile</CardTitle>
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-brand-2 text-lg font-bold text-white">
              {me.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
            </div>
            <div>
              <p className="font-semibold">{me.full_name}</p>
              <p className="text-sm text-muted">{me.email}</p>
              <p className="text-xs capitalize text-brand">{me.role}</p>
            </div>
          </div>
        </Card>

        <Card>
          <CardTitle className="mb-4 flex items-center gap-1.5"><Palette size={14} className="text-brand" /> Appearance</CardTitle>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Theme</p>
              <p className="text-xs text-muted">Switch between dark and light mode</p>
            </div>
            <Button variant="outline" onClick={toggle}>
              {dark ? <Sun size={15} /> : <Moon size={15} />} {dark ? "Light mode" : "Dark mode"}
            </Button>
          </div>
        </Card>

        <Card>
          <CardTitle className="mb-4 flex items-center gap-1.5"><Building2 size={14} className="text-brand" /> Business Details</CardTitle>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label>Business name</Label>
              <Input value={biz.name} onChange={(e) => set("name", e.target.value)} />
            </div>
            <div>
              <Label>Type</Label>
              <Select value={biz.business_type} onChange={(e) => set("business_type", e.target.value)}>
                {TYPES.map((t) => <option key={t}>{t}</option>)}
              </Select>
            </div>
            <div>
              <Label>Location</Label>
              <Input value={biz.location} onChange={(e) => set("location", e.target.value)} />
            </div>
            <div>
              <Label>Employees</Label>
              <Input type="number" value={biz.employees_count} onChange={(e) => set("employees_count", Number(e.target.value))} />
            </div>
            <div>
              <Label>Monthly customers</Label>
              <Input type="number" value={biz.customer_count} onChange={(e) => set("customer_count", Number(e.target.value))} />
            </div>
            <div>
              <Label>Monthly revenue (₹)</Label>
              <Input type="number" value={biz.monthly_revenue} onChange={(e) => set("monthly_revenue", Number(e.target.value))} />
            </div>
            <div>
              <Label>Monthly expenses (₹)</Label>
              <Input type="number" value={biz.monthly_expenses} onChange={(e) => set("monthly_expenses", Number(e.target.value))} />
            </div>
          </div>
          <Button className="mt-5" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save changes"}</Button>
        </Card>

        <Card>
          <CardTitle className="mb-3 flex items-center gap-1.5"><KeyRound size={14} className="text-brand" /> AI Integration</CardTitle>
          <p className="text-sm leading-relaxed text-ink-2">
            The AI Advisor uses <strong className="text-ink">Google Gemini</strong> when a <code className="rounded bg-brand-soft px-1.5 py-0.5 text-xs text-brand">GEMINI_API_KEY</code> is
            set in the backend&apos;s <code className="rounded bg-brand-soft px-1.5 py-0.5 text-xs text-brand">.env</code>. Without a key it falls back to the built-in
            Twin Engine advisor, which is grounded in the same live business data — so the demo always works offline.
          </p>
        </Card>
      </motion.div>
    </AppShell>
  );
}
