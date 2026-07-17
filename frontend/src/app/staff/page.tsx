"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, EmptyState, Input, Label, Modal, PageSkeleton, Select, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { Pencil, Plus, Trash2, UserRound, Users, Wallet } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Employee = { id: string; name: string; role: string; department: string; salary: number; performance: number };
type StaffData = {
  items: Employee[];
  options: { roles: string[]; departments: string[] };
  summary: { headcount: number; monthly_payroll: number; avg_salary: number; avg_performance_pct: number };
};

const EMPTY_FORM = { name: "", role: "Staff", department: "Operations", salary: "18000", performance: "80" };
type FormState = typeof EMPTY_FORM;

export default function StaffPage() {
  const { toast } = useToast();
  const [data, setData] = useState<StaffData | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api.get<StaffData>("/api/staff").then(setData).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const openAdd = () => { setEditing(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (e: Employee) => {
    setEditing(e);
    setForm({ name: e.name, role: e.role, department: e.department,
              salary: String(e.salary), performance: String(Math.round(e.performance * 100)) });
    setModalOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) { toast("Name is required", "critical"); return; }
    setSaving(true);
    const payload = {
      name: form.name.trim(), role: form.role, department: form.department,
      salary: Number(form.salary) || 0,
      performance: Math.min(Math.max(Number(form.performance) || 0, 0), 100) / 100,
    };
    try {
      if (editing) {
        await api.put(`/api/staff/${editing.id}`, payload);
        toast(`${payload.name} updated`, "good");
      } else {
        await api.post("/api/staff", payload);
        toast(`${payload.name} added to the team — simulator recalibrated`, "good");
      }
      setModalOpen(false);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not save", "critical");
    }
    setSaving(false);
  };

  const remove = async (e: Employee) => {
    try {
      await api.del(`/api/staff/${e.id}`);
      toast(`${e.name} removed — headcount synced`, "brand");
      load();
    } catch {
      toast("Could not remove", "critical");
    }
  };

  if (!data) return <AppShell title="Staff"><PageSkeleton /></AppShell>;
  const s = data.summary;

  return (
    <AppShell title="Staff">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Card className="flex items-center gap-3 px-4 py-3">
            <Users size={18} className="text-brand" />
            <div><p className="text-lg font-bold leading-none">{s.headcount}</p>
              <p className="text-[11px] text-muted">team members</p></div>
          </Card>
          <Card className="flex items-center gap-3 px-4 py-3">
            <Wallet size={18} className="text-brand" />
            <div><p className="text-lg font-bold leading-none">{inr(s.monthly_payroll)}</p>
              <p className="text-[11px] text-muted">monthly payroll · avg {inr(s.avg_salary)}</p></div>
          </Card>
          <Card className="flex items-center gap-3 px-4 py-3">
            <UserRound size={18} className="text-brand" />
            <div><p className="text-lg font-bold leading-none">{s.avg_performance_pct}%</p>
              <p className="text-[11px] text-muted">avg performance</p></div>
          </Card>
          <Button className="ml-auto" onClick={openAdd}><Plus size={15} /> Add employee</Button>
        </div>

        <Card>
          {data.items.length === 0 ? (
            <EmptyState icon={Users} title="No employees yet"
              hint="Add your team — headcount feeds the Simulator's staffing baseline automatically."
              action={<Button onClick={openAdd}><Plus size={15} /> Add your first employee</Button>} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                    <th className="pb-2 pr-3">Name</th><th className="pb-2 pr-3">Role</th>
                    <th className="pb-2 pr-3">Department</th>
                    <th className="pb-2 pr-3 text-right">Salary / month</th>
                    <th className="pb-2 pr-3">Performance</th>
                    <th className="pb-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id} className="border-b border-line last:border-0 transition-colors hover:bg-brand-soft/30">
                      <td className="py-2.5 pr-3 font-semibold">{e.name}</td>
                      <td className="py-2.5 pr-3 text-ink-2">{e.role}</td>
                      <td className="py-2.5 pr-3"><Badge tone="brand">{e.department}</Badge></td>
                      <td className="py-2.5 pr-3 text-right font-semibold tabular-nums">{inr(e.salary)}</td>
                      <td className="py-2.5 pr-3">
                        <span className="flex items-center gap-2">
                          <span className="h-1.5 w-20 overflow-hidden rounded-full bg-grid">
                            <span className="block h-full rounded-full bg-gradient-to-r from-brand to-brand-2"
                              style={{ width: `${Math.round(e.performance * 100)}%` }} />
                          </span>
                          <span className="text-xs tabular-nums text-ink-2">{Math.round(e.performance * 100)}%</span>
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <span className="inline-flex gap-1.5">
                          <Button variant="outline" size="sm" onClick={() => openEdit(e)} aria-label="Edit"><Pencil size={13} /></Button>
                          <Button variant="outline" size="sm" onClick={() => remove(e)} aria-label="Remove"><Trash2 size={13} /></Button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <p className="text-[11px] text-muted">
          Headcount and payroll flow straight into the twin: the Simulator&apos;s staffing lever, the
          finance expense breakdown and the understaffing risk check all recalibrate as you edit.
        </p>
      </motion.div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editing ? `Edit ${editing.name}` : "Add employee"}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><Label>Full name *</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ravi Kumar" /></div>
          <div><Label>Role</Label>
            <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {data.options.roles.map((r) => <option key={r}>{r}</option>)}
            </Select></div>
          <div><Label>Department</Label>
            <Select value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
              {data.options.departments.map((d) => <option key={d}>{d}</option>)}
            </Select></div>
          <div><Label>Monthly salary (₹)</Label>
            <Input type="number" min={0} value={form.salary} onChange={(e) => setForm({ ...form, salary: e.target.value })} /></div>
          <div><Label>Performance (%)</Label>
            <Input type="number" min={0} max={100} value={form.performance} onChange={(e) => setForm({ ...form, performance: e.target.value })} /></div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
          <Button onClick={save} disabled={saving}>{saving ? "Saving…" : editing ? "Save changes" : "Add employee"}</Button>
        </div>
      </Modal>
    </AppShell>
  );
}
