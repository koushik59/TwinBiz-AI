"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, EmptyState, Input, Label, PageSkeleton, Select, useToast } from "@/components/ui";
import { api, API_BASE, getToken } from "@/lib/api";
import { cn, inr, shortDate } from "@/lib/utils";
import { motion } from "framer-motion";
import { Ban, FileDown, Minus, Plus, Receipt, Search, ShoppingCart, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

type SimProduct = { id: string; name: string; category: string; price: number; cost: number; stock: number };
type BillItem = { product_id: string; name: string; qty: number; unit_price: number; line_total: number };
type Bill = {
  id: string; bill_no: string; status: string; customer_name: string; customer_phone: string;
  payment_method: string; items: BillItem[]; subtotal: number; discount_pct: number;
  discount_amount: number; total: number; tax_included: number; day: string; created_at: string;
};
type BillList = { items: Bill[]; summary: { today_bills: number; today_revenue: number } };

type CartLine = { product: SimProduct; qty: number };

export default function BillingPage() {
  const { toast } = useToast();
  const [products, setProducts] = useState<SimProduct[] | null>(null);
  const [bills, setBills] = useState<BillList | null>(null);
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [customer, setCustomer] = useState({ name: "", phone: "" });
  const [payment, setPayment] = useState("cash");
  const [discount, setDiscount] = useState("0");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get<{ items: SimProduct[] }>("/api/simulate/products").then((d) => setProducts(d.items)).catch(() => {});
    api.get<BillList>("/api/billing/bills?limit=30").then(setBills).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const filtered = useMemo(() => {
    if (!products) return [];
    const q = search.trim().toLowerCase();
    const base = q ? products.filter((p) => p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q)) : products;
    return base.slice(0, 24);
  }, [products, search]);

  const inCart = (id: string) => cart.find((l) => l.product.id === id);

  const add = (p: SimProduct) => {
    if (p.stock <= 0) { toast(`${p.name} is out of stock`, "critical"); return; }
    setCart((c) => {
      const line = c.find((l) => l.product.id === p.id);
      if (line) {
        if (line.qty >= p.stock) { toast(`Only ${p.stock} units of ${p.name} in stock`, "critical"); return c; }
        return c.map((l) => (l.product.id === p.id ? { ...l, qty: l.qty + 1 } : l));
      }
      return [...c, { product: p, qty: 1 }];
    });
  };

  const setQty = (id: string, qty: number) => {
    setCart((c) => c.flatMap((l) => {
      if (l.product.id !== id) return [l];
      if (qty <= 0) return [];
      if (qty > l.product.stock) { toast(`Only ${l.product.stock} units in stock`, "critical"); return [l]; }
      return [{ ...l, qty }];
    }));
  };

  const subtotal = cart.reduce((s, l) => s + l.qty * l.product.price, 0);
  const discountPct = Math.min(Math.max(Number(discount) || 0, 0), 90);
  const total = subtotal * (1 - discountPct / 100);

  const downloadPdf = async (bill: { id: string; bill_no: string }) => {
    const res = await fetch(`${API_BASE}/api/billing/bills/${bill.id}/pdf`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) { toast("Could not download the PDF", "critical"); return; }
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `${bill.bill_no}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const createBill = async () => {
    if (cart.length === 0) { toast("Add at least one product to the bill", "critical"); return; }
    setBusy(true);
    try {
      const bill = await api.post<Bill>("/api/billing/bills", {
        items: cart.map((l) => ({ product_id: l.product.id, qty: l.qty })),
        customer_name: customer.name, customer_phone: customer.phone,
        payment_method: payment, discount_pct: discountPct,
      });
      toast(`Bill ${bill.bill_no} created — stock & twin updated`, "good");
      await downloadPdf(bill);
      setCart([]);
      setCustomer({ name: "", phone: "" });
      setDiscount("0");
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create the bill", "critical");
    }
    setBusy(false);
  };

  const cancel = async (b: Bill) => {
    try {
      await api.post(`/api/billing/bills/${b.id}/cancel`);
      toast(`${b.bill_no} cancelled — stock restored, twin corrected`, "brand");
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not cancel", "critical");
    }
  };

  if (!products || !bills) return <AppShell title="Billing"><PageSkeleton /></AppShell>;

  return (
    <AppShell title="Billing">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Card className="flex items-center gap-3 px-4 py-3">
            <Receipt size={18} className="text-brand" />
            <div>
              <p className="text-lg font-bold leading-none">{bills.summary.today_bills}</p>
              <p className="text-[11px] text-muted">bills today</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 px-4 py-3">
            <ShoppingCart size={18} className="text-brand" />
            <div>
              <p className="text-lg font-bold leading-none">{inr(bills.summary.today_revenue)}</p>
              <p className="text-[11px] text-muted">billed today</p>
            </div>
          </Card>
          <p className="max-w-md text-xs leading-relaxed text-muted">
            Every bill automatically reduces stock and feeds real sales into your twin —
            dashboard, forecasts and risk analysis update with it.
          </p>
        </div>

        <div className="grid gap-5 lg:grid-cols-5">
          {/* product picker */}
          <Card className="lg:col-span-3">
            <div className="mb-3 flex items-center gap-2">
              <Search size={14} className="text-muted" />
              <Input placeholder="Search products…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="grid max-h-[430px] gap-2 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
              {filtered.map((p) => {
                const line = inCart(p.id);
                return (
                  <button key={p.id} onClick={() => add(p)}
                    className={cn("rounded-xl border p-3 text-left transition-all cursor-pointer",
                      line ? "border-brand bg-brand-soft/60" : "border-line hover:border-brand/40",
                      p.stock <= 0 && "opacity-40")}>
                    <p className="truncate text-sm font-semibold">{p.name}</p>
                    <p className="text-[11px] text-muted">{p.category} · {p.stock} in stock</p>
                    <p className="mt-1 flex items-center justify-between text-sm font-bold">
                      ₹{p.price}
                      {line && <Badge tone="brand">×{line.qty}</Badge>}
                    </p>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* cart */}
          <Card className="lg:col-span-2">
            <CardTitle className="mb-3 flex items-center gap-1.5"><ShoppingCart size={14} className="text-brand" /> Current bill</CardTitle>
            {cart.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted">Click products on the left to add them.</p>
            ) : (
              <div className="space-y-2">
                {cart.map((l) => (
                  <div key={l.product.id} className="flex items-center gap-2 border-b border-line pb-2 text-sm">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{l.product.name}</p>
                      <p className="text-[11px] text-muted">₹{l.product.price} each</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="sm" onClick={() => setQty(l.product.id, l.qty - 1)} aria-label="Less"><Minus size={12} /></Button>
                      <span className="w-7 text-center font-semibold tabular-nums">{l.qty}</span>
                      <Button variant="outline" size="sm" onClick={() => setQty(l.product.id, l.qty + 1)} aria-label="More"><Plus size={12} /></Button>
                    </div>
                    <span className="w-20 text-right font-semibold tabular-nums">{inr(l.qty * l.product.price)}</span>
                    <button onClick={() => setQty(l.product.id, 0)} className="text-muted transition-colors hover:text-critical cursor-pointer" aria-label="Remove">
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div><Label>Customer name (optional)</Label>
                <Input value={customer.name} onChange={(e) => setCustomer({ ...customer, name: e.target.value })} placeholder="Walk-in" /></div>
              <div><Label>Phone (tracks returning customers)</Label>
                <Input value={customer.phone} onChange={(e) => setCustomer({ ...customer, phone: e.target.value })} placeholder="98765 43210" /></div>
              <div><Label>Payment</Label>
                <Select value={payment} onChange={(e) => setPayment(e.target.value)}>
                  <option value="cash">Cash</option><option value="upi">UPI</option><option value="card">Card</option>
                </Select></div>
              <div><Label>Discount %</Label>
                <Input type="number" min={0} max={90} value={discount} onChange={(e) => setDiscount(e.target.value)} /></div>
            </div>

            <div className="mt-4 space-y-1 border-t border-line pt-3 text-sm">
              <p className="flex justify-between text-ink-2"><span>Subtotal</span><span className="tabular-nums">{inr(subtotal)}</span></p>
              {discountPct > 0 && (
                <p className="flex justify-between text-ink-2"><span>Discount ({discountPct}%)</span>
                  <span className="tabular-nums">− {inr(subtotal * discountPct / 100)}</span></p>
              )}
              <p className="flex justify-between text-base font-bold"><span>Total</span><span className="tabular-nums">{inr(total)}</span></p>
            </div>
            <Button className="mt-4 w-full" disabled={busy || cart.length === 0} onClick={createBill}>
              {busy ? "Creating…" : "Create Bill & Download PDF"} <FileDown size={15} />
            </Button>
          </Card>
        </div>

        {/* history */}
        <Card>
          <CardTitle className="mb-3">Recent bills</CardTitle>
          {bills.items.length === 0 ? (
            <EmptyState icon={Receipt} title="No bills yet" hint="Your first sale will appear here — and flow straight into the twin." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                    <th className="pb-2 pr-3">Bill</th><th className="pb-2 pr-3">Date</th>
                    <th className="pb-2 pr-3">Customer</th><th className="pb-2 pr-3">Items</th>
                    <th className="pb-2 pr-3 text-right">Total</th><th className="pb-2 pr-3">Payment</th>
                    <th className="pb-2 pr-3">Status</th><th className="pb-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {bills.items.map((b) => (
                    <tr key={b.id} className={cn("border-b border-line last:border-0", b.status === "cancelled" && "opacity-50")}>
                      <td className="py-2 pr-3 font-semibold">{b.bill_no}</td>
                      <td className="py-2 pr-3 text-ink-2">{shortDate(b.day)}</td>
                      <td className="py-2 pr-3 text-ink-2">{b.customer_name || "Walk-in"}</td>
                      <td className="py-2 pr-3 text-ink-2">{b.items.reduce((s, i) => s + i.qty, 0)} × {b.items.length} products</td>
                      <td className="py-2 pr-3 text-right font-semibold tabular-nums">{inr(b.total)}</td>
                      <td className="py-2 pr-3 uppercase text-ink-2">{b.payment_method}</td>
                      <td className="py-2 pr-3"><Badge tone={b.status === "paid" ? "good" : "critical"}>{b.status}</Badge></td>
                      <td className="py-2 text-right">
                        <span className="inline-flex gap-1.5">
                          <Button variant="outline" size="sm" onClick={() => downloadPdf(b)} aria-label="Download PDF"><FileDown size={13} /></Button>
                          {b.status === "paid" && (
                            <Button variant="outline" size="sm" onClick={() => cancel(b)} aria-label="Cancel bill"><Ban size={13} /></Button>
                          )}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </motion.div>
    </AppShell>
  );
}
