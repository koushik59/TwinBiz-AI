"use client";

import { AppShell } from "@/components/shell";
import { Badge, Card, CardTitle, PageSkeleton, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { AlertTriangle, Boxes, PackageCheck, Timer } from "lucide-react";
import { useEffect, useState } from "react";

type RestockItem = {
  product_id: number; name: string; stock: number; daily_demand: number;
  days_until_stockout: number; restock_by: string; suggested_order: number; status: string;
};
type TwinProduct = { id: number; name: string; category: string; stock: number; daily_demand: number; stock_value: number; days_of_stock: number; status: string; margin_pct: number };

export default function InventoryPage() {
  const [items, setItems] = useState<RestockItem[] | null>(null);
  const [products, setProducts] = useState<TwinProduct[]>([]);

  useEffect(() => {
    api.get<{ items: RestockItem[] }>("/api/simulate/restock").then((d) => setItems(d.items)).catch(() => {});
    api.get<{ products: TwinProduct[] }>("/api/business/twin").then((d) => setProducts(d.products)).catch(() => {});
  }, []);

  if (!items) {
    return (
      <AppShell title="Inventory Intelligence"><PageSkeleton /></AppShell>
    );
  }

  const totalValue = products.reduce((a, p) => a + p.stock_value, 0);
  const critical = items.filter((i) => i.status === "critical").length;
  const lowCount = items.filter((i) => i.status === "low").length;
  const fast = [...products].sort((a, b) => b.daily_demand - a.daily_demand).slice(0, 5);
  const slow = [...products].sort((a, b) => a.daily_demand - b.daily_demand).slice(0, 5);

  return (
    <AppShell title="Inventory Intelligence">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatTile label="Inventory Value" value={inr(totalValue)} icon={Boxes} />
          <StatTile label="SKUs Tracked" value={num(products.length)} icon={PackageCheck} />
          <StatTile label="Critical Stockouts" value={num(critical)} icon={AlertTriangle} hint={critical ? "Act today" : "All clear"} />
          <StatTile label="Low Stock Items" value={num(lowCount)} icon={Timer} />
        </div>

        <Card className="overflow-x-auto p-0">
          <div className="flex items-center justify-between p-4 pb-2">
            <CardTitle>Restock Predictions (ML)</CardTitle>
            <p className="text-xs text-muted">Sorted by urgency</p>
          </div>
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="px-4 py-2.5 font-semibold">Product</th>
                <th className="px-4 py-2.5 font-semibold">Status</th>
                <th className="px-4 py-2.5 text-right font-semibold">Stock</th>
                <th className="px-4 py-2.5 text-right font-semibold">Demand/day</th>
                <th className="px-4 py-2.5 text-right font-semibold">Stockout in</th>
                <th className="px-4 py-2.5 text-right font-semibold">Restock by</th>
                <th className="px-4 py-2.5 text-right font-semibold">Suggested order</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.product_id} className="border-b border-line last:border-0 transition-colors hover:bg-brand-soft/30">
                  <td className="px-4 py-3 font-medium">{i.name}</td>
                  <td className="px-4 py-3"><Badge tone={i.status}>{i.status}</Badge></td>
                  <td className="px-4 py-3 text-right tabular-nums">{num(i.stock)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{i.daily_demand}</td>
                  <td className={cn("px-4 py-3 text-right font-semibold tabular-nums", i.days_until_stockout < 5 ? "text-critical" : i.days_until_stockout < 12 ? "text-warning" : "text-ink-2")}>
                    {i.days_until_stockout}d
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-ink-2">{i.restock_by}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{i.suggested_order > 0 ? `${num(i.suggested_order)} units` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardTitle className="mb-3">🔥 Fast Movers</CardTitle>
            <div className="space-y-2">
              {fast.map((p, i) => (
                <div key={p.id} className="flex items-center gap-3 rounded-xl border border-line p-2.5">
                  <span className="w-5 text-center text-xs font-bold text-brand">#{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-muted">{p.daily_demand}/day · {p.margin_pct}% margin</p>
                  </div>
                  <Badge tone={p.status}>{p.days_of_stock}d cover</Badge>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <CardTitle className="mb-3">🐌 Slow Movers</CardTitle>
            <div className="space-y-2">
              {slow.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-xl border border-line p-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-muted">{p.daily_demand}/day · {inr(p.stock_value)} locked</p>
                  </div>
                  <Badge tone={p.status === "overstock" ? "overstock" : "low"}>{p.days_of_stock}d cover</Badge>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </motion.div>
    </AppShell>
  );
}
