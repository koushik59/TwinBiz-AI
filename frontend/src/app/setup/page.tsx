"use client";

import { Logo } from "@/components/shell";
import { Button, Card, Input, Label, Select, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { Building2, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

const TYPES = ["Supermarket", "Retail", "Restaurant", "Pharmacy", "Bakery", "Warehouse", "Manufacturing"];

export default function SetupPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [startMode, setStartMode] = useState<"demo" | "upload" | "manual">("demo");
  const [form, setForm] = useState({
    name: "",
    business_type: "Supermarket",
    location: "",
    employees_count: 5,
    monthly_revenue: 500000,
    monthly_expenses: 380000,
    customer_count: 1200,
    working_hours: "9:00-21:00",
  });

  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setLoading(true);
    try {
      await api.post("/api/business", { ...form, start_mode: startMode });
      if (startMode === "demo") {
        toast("Digital twin created with 365 days of demo intelligence ✨", "good");
        router.push("/dashboard");
      } else {
        toast("Twin created — bring in your real data next", "good");
        router.push(startMode === "upload" ? "/data-center" : "/products");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to create twin", "critical");
      setLoading(false);
    }
  };

  const steps = [
    {
      title: "Tell us about your business",
      body: (
        <div className="space-y-4">
          <div>
            <Label>Business name</Label>
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="FreshMart Supermarket" />
          </div>
          <div>
            <Label>Business type</Label>
            <div className="grid grid-cols-3 gap-2">
              {TYPES.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => set("business_type", t)}
                  className={`rounded-xl border px-2 py-2.5 text-xs font-medium transition-all cursor-pointer ${
                    form.business_type === t ? "border-brand bg-brand-soft text-brand" : "border-line text-ink-2 hover:bg-brand-soft"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div>
            <Label>Location</Label>
            <Input value={form.location} onChange={(e) => set("location", e.target.value)} placeholder="Hyderabad, Telangana" />
          </div>
        </div>
      ),
      valid: form.name.length > 1,
    },
    {
      title: "Your scale",
      body: (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Employees</Label>
              <Input type="number" min={1} value={form.employees_count} onChange={(e) => set("employees_count", Number(e.target.value))} />
            </div>
            <div>
              <Label>Monthly customers</Label>
              <Input type="number" min={10} value={form.customer_count} onChange={(e) => set("customer_count", Number(e.target.value))} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Monthly revenue (₹)</Label>
              <Input type="number" min={1000} value={form.monthly_revenue} onChange={(e) => set("monthly_revenue", Number(e.target.value))} />
            </div>
            <div>
              <Label>Monthly expenses (₹)</Label>
              <Input type="number" min={0} value={form.monthly_expenses} onChange={(e) => set("monthly_expenses", Number(e.target.value))} />
            </div>
          </div>
          <div>
            <Label>Working hours</Label>
            <Select value={form.working_hours} onChange={(e) => set("working_hours", e.target.value)}>
              <option>9:00-21:00</option>
              <option>8:00-22:00</option>
              <option>10:00-20:00</option>
              <option>24 hours</option>
            </Select>
          </div>
        </div>
      ),
      valid: form.monthly_revenue > 0,
    },
    {
      title: "How do you want to start?",
      body: (
        <div className="space-y-3">
          {([
            { key: "demo", title: "Use Demo Supermarket", desc: "365 days of realistic — clearly labeled — demo history, branded catalog, suppliers and staff. Best for exploring instantly." },
            { key: "upload", title: "Upload Real Business Data", desc: "Start empty, then import your products, sales and expenses from CSV/Excel in the Data Center." },
            { key: "manual", title: "Manual Setup", desc: "Start empty and add products, suppliers and employees by hand." },
          ] as const).map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => setStartMode(opt.key)}
              className={`block w-full rounded-xl border p-3.5 text-left transition-all cursor-pointer ${
                startMode === opt.key ? "border-brand bg-brand-soft shadow-sm" : "border-line hover:border-brand/40"
              }`}
            >
              <p className={`text-sm font-semibold ${startMode === opt.key ? "text-brand" : ""}`}>{opt.title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-ink-2">{opt.desc}</p>
            </button>
          ))}
          {startMode === "demo" && (
            <p className="flex items-start gap-2 text-xs text-muted">
              <Sparkles size={13} className="mt-0.5 shrink-0 text-brand" />
              Demo data is always labeled DEMO in the app and can be mixed with real imports later.
            </p>
          )}
        </div>
      ),
      valid: true,
    },
  ];

  const current = steps[step];

  return (
    <div className="aurora flex min-h-screen items-center justify-center p-4">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-lg">
        <div className="mb-6 flex justify-center"><Logo /></div>
        <Card className="p-7">
          <div className="mb-5 flex items-center gap-2">
            {steps.map((_, i) => (
              <div key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i <= step ? "bg-gradient-to-r from-brand to-brand-2" : "bg-grid"}`} />
            ))}
          </div>
          <div className="flex items-center gap-2 text-brand">
            <Building2 size={18} />
            <span className="text-xs font-semibold uppercase tracking-widest">Step {step + 1} of {steps.length}</span>
          </div>
          <h1 className="mt-2 text-lg font-semibold">{current.title}</h1>
          <div className="mt-5">{current.body}</div>
          <div className="mt-7 flex justify-between">
            <Button variant="ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>
              <ChevronLeft size={15} /> Back
            </Button>
            {step < steps.length - 1 ? (
              <Button onClick={() => setStep((s) => s + 1)} disabled={!current.valid}>
                Continue <ChevronRight size={15} />
              </Button>
            ) : (
              <Button onClick={submit} disabled={loading}>
                {loading ? "Building twin…" : "Create Digital Twin"} <Sparkles size={15} />
              </Button>
            )}
          </div>
        </Card>
      </motion.div>
    </div>
  );
}
