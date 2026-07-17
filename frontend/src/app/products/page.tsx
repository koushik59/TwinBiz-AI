"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, EmptyState, Input, Label, Modal, PageSkeleton, Select, StatTile, useToast } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, inr, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { ArrowDownAZ, ArrowUpZA, Boxes, ChevronLeft, ChevronRight, PackagePlus, Pencil, Percent, ShoppingBasket, Tag, Trash2, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Product = {
  on_sale: boolean; effective_price: number; sale_price: number | null; sale_ends: string | null;
  id: string; name: string; sku: string | null; barcode: string | null; brand: string | null;
  category: string; subcategory: string | null; description: string | null;
  unit_type: string | null; unit_size: string | null;
  price: number; cost: number; mrp: number | null; tax_rate: number | null;
  stock: number; min_stock: number | null; max_stock: number | null; safety_stock: number | null;
  reorder_level: number; reorder_qty: number | null; daily_demand: number;
  supplier_id: string | null; supplier_cost: number | null; lead_time_days: number | null; moq: number | null;
  expiry_days: number; storage_type: string | null; shelf_location: string | null;
  is_demo: boolean; margin_pct: number; days_of_stock: number; stock_status: string;
};
type Supplier = { id: string; name: string; category: string; lead_time_days: number };
type Summary = { count: number; inventory_value: number; low_stock: number; out_of_stock: number; demo_count: number; avg_margin_pct: number };

const EMPTY_FORM = {
  name: "", sku: "", barcode: "", brand: "", category: "General", subcategory: "",
  description: "", unit_type: "pcs", unit_size: "",
  price: "", cost: "", mrp: "", tax_rate: "",
  stock: "0", min_stock: "", max_stock: "", safety_stock: "", reorder_level: "15",
  reorder_qty: "", daily_demand: "5",
  supplier_id: "", supplier_cost: "", lead_time_days: "", moq: "",
  expiry_days: "0", storage_type: "ambient", shelf_location: "",
};
type FormState = typeof EMPTY_FORM;

function toPayload(f: FormState) {
  const numOrNull = (v: string) => (v.trim() === "" ? null : Number(v));
  const strOrNull = (v: string) => (v.trim() === "" ? null : v.trim());
  return {
    name: f.name.trim(), sku: strOrNull(f.sku), barcode: strOrNull(f.barcode),
    brand: strOrNull(f.brand), category: f.category.trim() || "General",
    subcategory: strOrNull(f.subcategory), description: strOrNull(f.description),
    unit_type: strOrNull(f.unit_type), unit_size: strOrNull(f.unit_size),
    price: Number(f.price), cost: Number(f.cost || 0),
    mrp: numOrNull(f.mrp), tax_rate: numOrNull(f.tax_rate),
    stock: Number(f.stock || 0), min_stock: numOrNull(f.min_stock),
    max_stock: numOrNull(f.max_stock), safety_stock: numOrNull(f.safety_stock),
    reorder_level: Number(f.reorder_level || 0), reorder_qty: numOrNull(f.reorder_qty),
    daily_demand: Number(f.daily_demand || 0),
    supplier_id: strOrNull(f.supplier_id), supplier_cost: numOrNull(f.supplier_cost),
    lead_time_days: numOrNull(f.lead_time_days), moq: numOrNull(f.moq),
    expiry_days: Number(f.expiry_days || 0), storage_type: strOrNull(f.storage_type),
    shelf_location: strOrNull(f.shelf_location),
  };
}

function productToForm(p: Product): FormState {
  const s = (v: number | string | null | undefined) => (v === null || v === undefined ? "" : String(v));
  return {
    name: p.name, sku: s(p.sku), barcode: s(p.barcode), brand: s(p.brand),
    category: p.category, subcategory: s(p.subcategory), description: s(p.description),
    unit_type: s(p.unit_type) || "pcs", unit_size: s(p.unit_size),
    price: s(p.price), cost: s(p.cost), mrp: s(p.mrp), tax_rate: s(p.tax_rate),
    stock: s(p.stock), min_stock: s(p.min_stock), max_stock: s(p.max_stock),
    safety_stock: s(p.safety_stock), reorder_level: s(p.reorder_level),
    reorder_qty: s(p.reorder_qty), daily_demand: s(p.daily_demand),
    supplier_id: s(p.supplier_id), supplier_cost: s(p.supplier_cost),
    lead_time_days: s(p.lead_time_days), moq: s(p.moq),
    expiry_days: s(p.expiry_days), storage_type: s(p.storage_type) || "ambient",
    shelf_location: s(p.shelf_location),
  };
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

export default function ProductsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<Product[] | null>(null);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<string[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("name");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Product | null>(null);

  const [stockFor, setStockFor] = useState<Product | null>(null);
  const [stockForm, setStockForm] = useState({ mode: "add", qty: "", reason: "delivery", note: "" });
  const [saleFor, setSaleFor] = useState<Product | null>(null);
  const [saleForm, setSaleForm] = useState({ price: "", ends: "" });

  const load = useCallback(() => {
    const params = new URLSearchParams({
      search, category, sort, order, page: String(page), page_size: String(pageSize),
    });
    api.get<{ items: Product[]; total: number; categories: string[] }>(`/api/products?${params}`)
      .then((d) => { setItems(d.items); setTotal(d.total); setCategories(d.categories); })
      .catch(() => setItems([]));
    api.get<Summary>("/api/products/summary").then(setSummary).catch(() => {});
  }, [search, category, sort, order, page]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0); // debounce typing
    return () => clearTimeout(t);
  }, [load, search]);

  useEffect(() => {
    api.get<{ items: Supplier[] }>("/api/products/suppliers").then((d) => setSuppliers(d.items)).catch(() => {});
  }, []);

  const openAdd = () => { setEditing(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (p: Product) => { setEditing(p); setForm(productToForm(p)); setModalOpen(true); };

  const save = async () => {
    if (!form.name.trim() || !form.price || Number(form.price) <= 0) {
      toast("Product name and a selling price above 0 are required", "critical");
      return;
    }
    if (form.mrp && Number(form.mrp) < Number(form.price)) {
      toast("MRP cannot be below the selling price", "critical");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/api/products/${editing.id}`, toPayload(form));
        toast("Product updated", "good");
      } else {
        await api.post("/api/products", toPayload(form));
        toast("Product added", "good");
      }
      setModalOpen(false);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Failed to save product", "critical");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    try {
      await api.del(`/api/products/${deleting.id}`);
      toast(`Deleted ${deleting.name}`, "good");
      setDeleting(null);
      load();
    } catch {
      toast("Failed to delete product", "critical");
    }
  };

  const adjustStock = async () => {
    if (!stockFor) return;
    const qty = Math.abs(Number(stockForm.qty) || 0);
    if (qty <= 0) { toast("Enter a quantity above 0", "critical"); return; }
    const delta = stockForm.mode === "add" ? qty : -qty;
    try {
      await api.post(`/api/products/${stockFor.id}/stock`, {
        delta, reason: stockForm.mode === "add" ? "delivery" : stockForm.reason, note: stockForm.note,
      });
      toast(`${stockFor.name}: stock ${delta > 0 ? "+" : ""}${delta} recorded`, "good");
      setStockFor(null);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not adjust stock", "critical");
    }
  };

  const applySale = async () => {
    if (!saleFor) return;
    const price = Number(saleForm.price);
    if (!price || price <= 0) { toast("Enter a valid sale price", "critical"); return; }
    try {
      await api.put(`/api/products/${saleFor.id}/sale`, {
        sale_price: price, sale_ends: saleForm.ends || null,
      });
      toast(`${saleFor.name} on sale at ₹${price}${saleForm.ends ? ` until ${saleForm.ends}` : ""} — billing charges it automatically`, "good");
      setSaleFor(null);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not set the sale price", "critical");
    }
  };

  const clearSale = async () => {
    if (!saleFor) return;
    try {
      await api.del(`/api/products/${saleFor.id}/sale`);
      toast(`${saleFor.name} back to regular price`, "brand");
      setSaleFor(null);
      load();
    } catch {
      toast("Could not remove the sale", "critical");
    }
  };

  const toggleSort = (col: string) => {
    if (sort === col) setOrder(order === "asc" ? "desc" : "asc");
    else { setSort(col); setOrder("asc"); }
  };

  const pages = Math.max(Math.ceil(total / pageSize), 1);

  if (!items) return <AppShell title="Products"><PageSkeleton /></AppShell>;

  const SortHead = ({ col, children, right = false }: { col: string; children: React.ReactNode; right?: boolean }) => (
    <th className={cn("cursor-pointer select-none px-4 py-2.5 font-semibold hover:text-ink", right && "text-right")}
        onClick={() => toggleSort(col)}>
      <span className="inline-flex items-center gap-1">
        {children}
        {sort === col && (order === "asc" ? <ArrowDownAZ size={12} /> : <ArrowUpZA size={12} />)}
      </span>
    </th>
  );

  return (
    <AppShell title="Products">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatTile label="Products" value={num(summary?.count ?? total)} icon={ShoppingBasket} />
          <StatTile label="Inventory Value" value={inr(summary?.inventory_value)} icon={Boxes} />
          <StatTile label="Low / Out of Stock" value={`${num(summary?.low_stock)} / ${num(summary?.out_of_stock)}`} icon={TriangleAlert} />
          <StatTile label="Avg Margin" value={summary ? `${summary.avg_margin_pct}%` : "—"} icon={Percent} />
        </div>

        <Card className="p-0">
          <div className="flex flex-wrap items-center gap-2 p-4 pb-3">
            <Input placeholder="Search name, SKU, brand…" value={search}
                   onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="max-w-xs" />
            <Select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className="max-w-[180px]">
              <option value="">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <div className="ml-auto">
              <Button size="sm" onClick={openAdd}><PackagePlus size={15} /> Add Product</Button>
            </div>
          </div>

          {items.length === 0 ? (
            <div className="p-4">
              <EmptyState icon={ShoppingBasket} title="No products found"
                hint={search || category ? "Try a different search or filter." : "Add your first product or import your catalog in the Data Center."}
                action={<Button size="sm" onClick={openAdd}><PackagePlus size={15} /> Add Product</Button>} />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                    <SortHead col="name">Product</SortHead>
                    <SortHead col="category">Category</SortHead>
                    <SortHead col="price" right>Price</SortHead>
                    <SortHead col="cost" right>Cost</SortHead>
                    <th className="px-4 py-2.5 text-right font-semibold">Margin</th>
                    <SortHead col="stock" right>Stock</SortHead>
                    <th className="px-4 py-2.5 font-semibold">Status</th>
                    <th className="px-4 py-2.5 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((p) => (
                    <tr key={p.id} className="border-b border-line last:border-0 transition-colors hover:bg-brand-soft/30">
                      <td className="px-4 py-3">
                        <p className="font-medium">{p.name}</p>
                        <p className="text-xs text-muted">
                          {p.sku}{p.brand ? ` · ${p.brand}` : ""}{p.unit_size ? ` · ${p.unit_size}` : ""}
                          {p.is_demo && <Badge tone="brand" className="ml-2">demo</Badge>}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-ink-2">{p.category}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {p.on_sale ? (
                          <span className="inline-flex items-center gap-1.5">
                            <Badge tone="good">SALE</Badge>
                            <span className="font-semibold">{inr(p.effective_price, false)}</span>
                            <span className="text-xs text-muted line-through">{inr(p.price, false)}</span>
                          </span>
                        ) : inr(p.price, false)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-2">{inr(p.cost, false)}</td>
                      <td className={cn("px-4 py-3 text-right font-medium tabular-nums", p.margin_pct < 8 ? "text-critical" : "text-ink-2")}>{p.margin_pct}%</td>
                      <td className="px-4 py-3 text-right tabular-nums">{num(p.stock)}</td>
                      <td className="px-4 py-3"><Badge tone={p.stock_status}>{p.stock_status}</Badge></td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => { setStockFor(p); setStockForm({ mode: "add", qty: "", reason: "damaged", note: "" }); }}
                                aria-label={`Adjust stock of ${p.name}`} title="Adjust stock"
                                className="rounded-lg p-1.5 text-ink-2 hover:bg-brand-soft hover:text-brand cursor-pointer">
                          <PackagePlus size={15} />
                        </button>
                        <button onClick={() => { setSaleFor(p); setSaleForm({ price: p.sale_price ? String(p.sale_price) : "", ends: p.sale_ends ?? "" }); }}
                                aria-label={`Sale price for ${p.name}`} title="Temporary sale price"
                                className={cn("rounded-lg p-1.5 cursor-pointer",
                                  p.on_sale ? "text-[var(--delta-good)] hover:bg-brand-soft" : "text-ink-2 hover:bg-brand-soft hover:text-brand")}>
                          <Tag size={15} />
                        </button>
                        <button onClick={() => openEdit(p)} aria-label={`Edit ${p.name}`} title="Edit"
                                className="rounded-lg p-1.5 text-ink-2 hover:bg-brand-soft hover:text-brand cursor-pointer">
                          <Pencil size={15} />
                        </button>
                        <button onClick={() => setDeleting(p)} aria-label={`Delete ${p.name}`} title="Delete"
                                className="rounded-lg p-1.5 text-ink-2 hover:bg-critical/10 hover:text-critical cursor-pointer">
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-xs text-muted">
            <span>{num(total)} products · page {page} of {pages}</span>
            <div className="flex gap-1">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={14} /></Button>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}><ChevronRight size={14} /></Button>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* add / edit modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? `Edit ${editing.name}` : "Add Product"} wide>
        <div className="max-h-[65vh] space-y-5 overflow-y-auto pr-1">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Basic Information</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2"><Field label="Product Name *"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Amul Milk 500ml" /></Field></div>
              <Field label="SKU"><Input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} placeholder="auto-generated" /></Field>
              <Field label="Brand"><Input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} /></Field>
              <Field label="Category"><Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} list="product-categories" /></Field>
              <Field label="Subcategory"><Input value={form.subcategory} onChange={(e) => setForm({ ...form, subcategory: e.target.value })} /></Field>
              <Field label="Unit Type">
                <Select value={form.unit_type} onChange={(e) => setForm({ ...form, unit_type: e.target.value })}>
                  {["pcs", "kg", "g", "L", "ml", "pack", "box", "dozen"].map((u) => <option key={u}>{u}</option>)}
                </Select>
              </Field>
              <Field label="Unit Size"><Input value={form.unit_size} onChange={(e) => setForm({ ...form, unit_size: e.target.value })} placeholder="500ml" /></Field>
              <Field label="Barcode"><Input value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} /></Field>
              <div className="sm:col-span-3"><Field label="Description"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div>
            </div>
            <datalist id="product-categories">{categories.map((c) => <option key={c} value={c} />)}</datalist>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Pricing</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Selling Price (₹) *"><Input type="number" min={0} value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></Field>
              <Field label="Cost Price (₹) *"><Input type="number" min={0} value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} /></Field>
              <Field label="MRP (₹)"><Input type="number" min={0} value={form.mrp} onChange={(e) => setForm({ ...form, mrp: e.target.value })} /></Field>
              <Field label="Tax Rate (%)"><Input type="number" min={0} max={100} value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} /></Field>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Inventory</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Current Stock"><Input type="number" min={0} value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} /></Field>
              <Field label="Avg Daily Sales"><Input type="number" min={0} step="0.1" value={form.daily_demand} onChange={(e) => setForm({ ...form, daily_demand: e.target.value })} /></Field>
              <Field label="Reorder Point"><Input type="number" min={0} value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} /></Field>
              <Field label="Reorder Quantity"><Input type="number" min={0} value={form.reorder_qty} onChange={(e) => setForm({ ...form, reorder_qty: e.target.value })} /></Field>
              <Field label="Minimum Stock"><Input type="number" min={0} value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: e.target.value })} /></Field>
              <Field label="Maximum Stock"><Input type="number" min={0} value={form.max_stock} onChange={(e) => setForm({ ...form, max_stock: e.target.value })} /></Field>
              <Field label="Safety Stock"><Input type="number" min={0} value={form.safety_stock} onChange={(e) => setForm({ ...form, safety_stock: e.target.value })} /></Field>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Supplier</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Supplier">
                <Select value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}>
                  <option value="">— none —</option>
                  {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </Select>
              </Field>
              <Field label="Supplier Cost (₹)"><Input type="number" min={0} value={form.supplier_cost} onChange={(e) => setForm({ ...form, supplier_cost: e.target.value })} /></Field>
              <Field label="Lead Time (days)"><Input type="number" min={0} value={form.lead_time_days} onChange={(e) => setForm({ ...form, lead_time_days: e.target.value })} /></Field>
              <Field label="Min Order Qty"><Input type="number" min={0} value={form.moq} onChange={(e) => setForm({ ...form, moq: e.target.value })} /></Field>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Product Behaviour</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Shelf Life (days, 0 = none)"><Input type="number" min={0} value={form.expiry_days} onChange={(e) => setForm({ ...form, expiry_days: e.target.value })} /></Field>
              <Field label="Storage Type">
                <Select value={form.storage_type} onChange={(e) => setForm({ ...form, storage_type: e.target.value })}>
                  {["ambient", "refrigerated", "frozen"].map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Field>
              <Field label="Shelf Location"><Input value={form.shelf_location} onChange={(e) => setForm({ ...form, shelf_location: e.target.value })} placeholder="Aisle 3, Eye Level" /></Field>
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2 border-t border-line pt-4">
          <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
          <Button onClick={save} disabled={saving}>{saving ? "Saving…" : editing ? "Save Changes" : "Add Product"}</Button>
        </div>
      </Modal>

      {/* stock adjust */}
      <Modal open={!!stockFor} onClose={() => setStockFor(null)} title={`Adjust stock — ${stockFor?.name ?? ""}`}>
        <p className="text-xs text-muted">Current stock: <strong className="text-ink">{num(stockFor?.stock)}</strong> units.
          Adjustments are logged with a reason so your inventory trail stays auditable.</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <Label>Action</Label>
            <Select value={stockForm.mode} onChange={(e) => setStockForm({ ...stockForm, mode: e.target.value })}>
              <option value="add">Receive stock (+)</option>
              <option value="remove">Remove stock (−)</option>
            </Select>
          </div>
          <div>
            <Label>Quantity</Label>
            <Input type="number" min={1} value={stockForm.qty} autoFocus
                   onChange={(e) => setStockForm({ ...stockForm, qty: e.target.value })} placeholder="e.g. 50" />
          </div>
          {stockForm.mode === "remove" && (
            <div>
              <Label>Reason</Label>
              <Select value={stockForm.reason} onChange={(e) => setStockForm({ ...stockForm, reason: e.target.value })}>
                <option value="damaged">Damaged</option>
                <option value="expired">Expired</option>
                <option value="theft">Theft / loss</option>
                <option value="correction">Count correction</option>
              </Select>
            </div>
          )}
          <div className={stockForm.mode === "remove" ? "" : "sm:col-span-2"}>
            <Label>Note (optional)</Label>
            <Input value={stockForm.note} onChange={(e) => setStockForm({ ...stockForm, note: e.target.value })}
                   placeholder={stockForm.mode === "add" ? "e.g. Metro Wholesale delivery" : "e.g. cold storage failure"} />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setStockFor(null)}>Cancel</Button>
          <Button onClick={adjustStock}>{stockForm.mode === "add" ? "Receive stock" : "Remove stock"}</Button>
        </div>
      </Modal>

      {/* temporary sale price */}
      <Modal open={!!saleFor} onClose={() => setSaleFor(null)} title={`Temporary sale price — ${saleFor?.name ?? ""}`}>
        <p className="text-xs text-muted">
          Regular price <strong className="text-ink">{inr(saleFor?.price, false)}</strong> · cost {inr(saleFor?.cost, false)}.
          While the sale is active, <strong className="text-ink">Billing charges this price automatically</strong>;
          it reverts on the end date (or when you remove it).
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <Label>Sale price (₹)</Label>
            <Input type="number" min={1} value={saleForm.price} autoFocus
                   onChange={(e) => setSaleForm({ ...saleForm, price: e.target.value })}
                   placeholder={saleFor ? String(Math.round(saleFor.price * 0.9)) : ""} />
          </div>
          <div>
            <Label>Ends on (optional)</Label>
            <Input type="date" value={saleForm.ends}
                   onChange={(e) => setSaleForm({ ...saleForm, ends: e.target.value })} />
          </div>
        </div>
        {saleFor && Number(saleForm.price) > 0 && Number(saleForm.price) < saleFor.cost && (
          <p className="mt-2 text-xs font-medium text-critical">
            ⚠ Below cost ({inr(saleFor.cost, false)}) — you&apos;ll lose money on every unit. Fine for clearance, just so you know.
          </p>
        )}
        <div className="mt-5 flex justify-between gap-2">
          {saleFor?.on_sale ? (
            <Button variant="outline" onClick={clearSale}>Remove sale</Button>
          ) : <span />}
          <span className="flex gap-2">
            <Button variant="outline" onClick={() => setSaleFor(null)}>Cancel</Button>
            <Button onClick={applySale}>{saleFor?.on_sale ? "Update sale" : "Start sale"}</Button>
          </span>
        </div>
      </Modal>

      {/* delete confirm */}
      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Delete product?">
        <p className="text-sm text-ink-2">
          <strong>{deleting?.name}</strong> and its sales history rows will be removed from the twin. This cannot be undone.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="danger" onClick={confirmDelete}>Delete</Button>
        </div>
      </Modal>
    </AppShell>
  );
}
