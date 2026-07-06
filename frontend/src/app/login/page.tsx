"use client";

import { Logo } from "@/components/shell";
import { Button, Card, Input, Label, useToast } from "@/components/ui";
import { api, setToken } from "@/lib/api";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [email, setEmail] = useState("demo@twinbiz.ai");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string; has_business: boolean }>("/api/auth/login", { email, password });
      setToken(res.access_token);
      router.push(res.has_business ? "/dashboard" : "/setup");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Login failed", "critical");
      setLoading(false);
    }
  };

  return (
    <div className="aurora flex min-h-screen items-center justify-center p-4">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
        <div className="mb-6 flex justify-center"><Logo /></div>
        <Card className="p-7">
          <h1 className="text-lg font-semibold">Welcome back</h1>
          <p className="mt-0.5 text-xs text-muted">Sign in to your digital twin. Demo credentials are pre-filled.</p>
          <form onSubmit={submit} className="mt-5 space-y-4">
            <div>
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </div>
            <div>
              <Label>Password</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            </div>
            <Button className="w-full" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</Button>
          </form>
          <p className="mt-4 text-center text-xs text-muted">
            No account?{" "}
            <Link href="/register" className="font-semibold text-brand hover:underline">Create one free</Link>
          </p>
        </Card>
      </motion.div>
    </div>
  );
}
