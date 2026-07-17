"use client";

import { GoogleAuthButton } from "@/components/google-auth";
import { Logo } from "@/components/shell";
import { Button, Card, Input, Label, useToast } from "@/components/ui";
import { api, setToken } from "@/lib/api";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function RegisterPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string }>("/api/auth/register", form);
      setToken(res.access_token);
      toast("Account created! Now build your twin.", "good");
      router.push("/setup");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Registration failed", "critical");
      setLoading(false);
    }
  };

  return (
    <div className="aurora flex min-h-screen items-center justify-center p-4">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
        <div className="mb-6 flex justify-center"><Logo /></div>
        <Card className="p-7">
          <h1 className="text-lg font-semibold">Create your account</h1>
          <p className="mt-0.5 text-xs text-muted">Two minutes to your first simulation.</p>
          <form onSubmit={submit} className="mt-5 space-y-4">
            <div>
              <Label>Full name</Label>
              <Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required placeholder="Ramesh Gupta" />
            </div>
            <div>
              <Label>Email</Label>
              <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required placeholder="you@business.com" />
            </div>
            <div>
              <Label>Password</Label>
              <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} placeholder="At least 6 characters" />
            </div>
            <Button className="w-full" disabled={loading}>{loading ? "Creating…" : "Create account"}</Button>
          </form>
          <GoogleAuthButton />
          <p className="mt-4 text-center text-xs text-muted">
            Already registered?{" "}
            <Link href="/login" className="font-semibold text-brand hover:underline">Sign in</Link>
          </p>
        </Card>
      </motion.div>
    </div>
  );
}
