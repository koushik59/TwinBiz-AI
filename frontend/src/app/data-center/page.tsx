"use client";

import { AppShell } from "@/components/shell";
import { Badge, Button, Card, CardTitle, Select, useToast } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, num } from "@/lib/utils";
import { motion } from "framer-motion";
import { Boxes, CheckCircle2, ChevronLeft, CloudUpload, Database, FileSpreadsheet, IndianRupee, ReceiptText, ShoppingCart, Truck, UserRound, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

type DataType = "products" | "sales" | "daily_metrics" | "expenses" | "suppliers" | "employees";

const TYPES: { key: DataType; label: string; desc: string; icon: typeof Boxes }[] = [
  { key: "products", label: "Products", desc: "Catalog: names, SKUs, prices, stock", icon: Boxes },
  { key: "sales", label: "Product Sales", desc: "Units sold per product per day", icon: ShoppingCart },
  { key: "daily_metrics", label: "Daily Business Totals", desc: "Revenue, expenses, customers by day", icon: IndianRupee },
  { key: "expenses", label: "Expenses", desc: "Dated expense entries", icon: ReceiptText },
  { key: "suppliers", label: "Suppliers", desc: "Vendors, lead times, reliability", icon: Truck },
  { key: "employees", label: "Employees", desc: "Team members, roles, salaries", icon: UserRound },
];

type Preview = {
  columns: string[];
  row_count: number;
  sample: Record<string, string | number | null>[];
  suggested_mapping: Record<string, string | null>;
  target_fields: { field: string; required: boolean; kind: string }[];
};
type Report = {
  total: number; valid: number; invalid: number; duplicates: number;
  errors: { row: number | null; problem: string }[];
  warnings: { row: number | null; problem: string }[];
};
type ImportResult = { report: Report; committed: boolean; created?: number; updated?: number; skipped?: number; data_source: string };
type Status = { data_source: string; counts: Record<string, number> };

export default function DataCenterPage() {
  const { toast } = useToast();
  const [status, setStatus] = useState<Status | null>(null);
  const [dataType, setDataType] = useState<DataType | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [validation, setValidation] = useState<ImportResult | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadStatus = useCallback(() => {
    api.get<Status>("/api/data-center/status").then(setStatus).catch(() => {});
  }, []);
  useEffect(loadStatus, [loadStatus]);

  const reset = () => {
    setDataType(null); setFile(null); setPreview(null);
    setMapping({}); setValidation(null); setResult(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const onFile = async (f: File | null) => {
    if (!f || !dataType) return;
    setFile(f); setPreview(null); setValidation(null); setResult(null);
    const form = new FormData();
    form.append("data_type", dataType);
    form.append("file", f);
    setBusy(true);
    try {
      const p = await api.upload<Preview>("/api/data-center/preview", form);
      setPreview(p);
      setMapping(p.suggested_mapping);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not read that file", "critical");
      setFile(null);
    } finally {
      setBusy(false);
    }
  };

  const runImport = async (commit: boolean) => {
    if (!file || !dataType) return;
    const form = new FormData();
    form.append("data_type", dataType);
    form.append("mapping", JSON.stringify(mapping));
    form.append("commit", String(commit));
    form.append("file", file);
    setBusy(true);
    try {
      const r = await api.upload<ImportResult>("/api/data-center/import", form);
      if (commit) {
        setResult(r);
        toast(`Imported ${r.created ?? 0} new + ${r.updated ?? 0} updated rows`, "good");
        loadStatus();
      } else {
        setValidation(r);
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Import failed", "critical");
    } finally {
      setBusy(false);
    }
  };

  const requiredUnmapped = preview
    ? preview.target_fields.filter((t) => t.required && !Object.values(mapping).includes(t.field)).map((t) => t.field)
    : [];

  return (
    <AppShell title="Data Center">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        {/* twin data status */}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-brand-soft p-2.5 text-brand"><Database size={18} /></div>
              <div>
                <p className="text-sm font-semibold">Twin data source</p>
                <p className="text-xs text-muted">What your digital twin is currently built from</p>
              </div>
            </div>
            {status && (
              <Badge tone={status.data_source === "real" ? "good" : status.data_source === "mixed" ? "medium" : "brand"}>
                {status.data_source === "demo" ? "DEMO DATA" : status.data_source === "mixed" ? "DEMO + REAL DATA" : "REAL DATA"}
              </Badge>
            )}
          </div>
          {status && (
            <div className="mt-4 grid grid-cols-2 gap-3 text-center sm:grid-cols-3 lg:grid-cols-6">
              {[
                ["Products", status.counts.products],
                ["· demo", status.counts.demo_products],
                ["· real", status.counts.real_products],
                ["Days of history", status.counts.daily_metrics],
                ["Sales rows", status.counts.product_sales],
                ["Suppliers", status.counts.suppliers],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-xl border border-line p-2.5">
                  <p className="text-lg font-semibold tabular-nums">{num(value as number)}</p>
                  <p className="text-[11px] text-muted">{label}</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* step 1: choose type */}
        <Card>
          <CardTitle className="mb-3">1 · What are you importing?</CardTitle>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {TYPES.map((t) => (
              <button
                key={t.key}
                onClick={() => { reset(); setDataType(t.key); }}
                className={cn(
                  "flex items-start gap-3 rounded-xl border p-3.5 text-left transition-all cursor-pointer",
                  dataType === t.key ? "border-brand bg-brand-soft shadow-sm" : "border-line hover:border-brand/40 hover:bg-brand-soft/40"
                )}
              >
                <t.icon size={18} className={dataType === t.key ? "text-brand" : "text-muted"} />
                <span>
                  <span className="block text-sm font-medium">{t.label}</span>
                  <span className="block text-xs text-muted">{t.desc}</span>
                </span>
              </button>
            ))}
          </div>
        </Card>

        {/* step 2: upload */}
        {dataType && (
          <Card>
            <CardTitle className="mb-3">2 · Upload CSV or Excel file</CardTitle>
            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line px-6 py-10 text-center transition-colors hover:border-brand/50 hover:bg-brand-soft/30">
              <CloudUpload size={26} className="text-brand" />
              <span className="text-sm font-medium">{file ? file.name : "Click to choose a .csv or .xlsx file"}</span>
              <span className="text-xs text-muted">Max 5 MB · 5,000 rows · first row must be column headers</span>
              <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
                     onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
            </label>
          </Card>
        )}

        {/* step 3: mapping + sample */}
        {preview && (
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <CardTitle>3 · Map your columns</CardTitle>
              <p className="text-xs text-muted">{num(preview.row_count)} rows detected</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {preview.columns.map((col) => (
                <div key={col} className="rounded-xl border border-line p-2.5">
                  <p className="mb-1 truncate text-xs font-semibold" title={col}>{col}</p>
                  <Select
                    value={mapping[col] ?? ""}
                    onChange={(e) => setMapping({ ...mapping, [col]: e.target.value || null })}
                    className="h-9 text-xs"
                  >
                    <option value="">— ignore —</option>
                    {preview.target_fields.map((t) => (
                      <option key={t.field} value={t.field}>
                        {t.field}{t.required ? " *" : ""}
                      </option>
                    ))}
                  </Select>
                </div>
              ))}
            </div>
            {requiredUnmapped.length > 0 && (
              <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-warning">
                <XCircle size={13} /> Required fields not mapped: {requiredUnmapped.join(", ")}
              </p>
            )}

            <div className="mt-4 overflow-x-auto rounded-xl border border-line">
              <table className="w-full min-w-[600px] text-xs">
                <thead>
                  <tr className="border-b border-line bg-brand-soft/40 text-left text-muted">
                    {preview.columns.map((c) => (
                      <th key={c} className="px-3 py-2 font-semibold">
                        {c}
                        {mapping[c] && <span className="ml-1 text-brand">→ {mapping[c]}</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.sample.map((row, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      {preview.columns.map((c) => (
                        <td key={c} className="px-3 py-1.5 text-ink-2">{row[c] === null ? "—" : String(row[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex justify-end">
              <Button onClick={() => runImport(false)} disabled={busy || requiredUnmapped.length > 0}>
                {busy ? "Validating…" : "Validate Data"}
              </Button>
            </div>
          </Card>
        )}

        {/* step 4: validation report */}
        {validation && !result && (
          <Card>
            <CardTitle className="mb-3">4 · Validation report</CardTitle>
            <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
              {[
                ["Total rows", validation.report.total, "text-ink"],
                ["Valid", validation.report.valid, "text-good"],
                ["Invalid", validation.report.invalid, "text-critical"],
                ["Duplicates", validation.report.duplicates, "text-warning"],
              ].map(([label, value, tone]) => (
                <div key={label as string} className="rounded-xl border border-line p-3">
                  <p className={cn("text-2xl font-semibold tabular-nums", tone as string)}>{num(value as number)}</p>
                  <p className="text-[11px] text-muted">{label}</p>
                </div>
              ))}
            </div>

            {(validation.report.errors.length > 0 || validation.report.warnings.length > 0) && (
              <div className="mt-4 max-h-56 space-y-1.5 overflow-y-auto rounded-xl border border-line p-3">
                {validation.report.errors.map((e, i) => (
                  <p key={`e${i}`} className="flex items-start gap-1.5 text-xs text-critical">
                    <XCircle size={13} className="mt-0.5 shrink-0" />
                    {e.row ? `Row ${e.row}: ` : ""}{e.problem}
                  </p>
                ))}
                {validation.report.warnings.map((w, i) => (
                  <p key={`w${i}`} className="flex items-start gap-1.5 text-xs text-warning">
                    <XCircle size={13} className="mt-0.5 shrink-0" />
                    {w.row ? `Row ${w.row}: ` : ""}{w.problem}
                  </p>
                ))}
              </div>
            )}

            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-muted">
                Only the {num(validation.report.valid)} valid rows will be imported. Invalid rows are never silently dropped — fix them and re-upload if needed.
              </p>
              <Button onClick={() => runImport(true)} disabled={busy || validation.report.valid === 0}>
                {busy ? "Importing…" : `Import ${num(validation.report.valid)} rows`}
              </Button>
            </div>
          </Card>
        )}

        {/* step 5: result */}
        {result && (
          <Card className="border-good/40">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={22} className="text-good" />
              <div>
                <p className="text-sm font-semibold">Import complete</p>
                <p className="text-xs text-ink-2">
                  {num(result.created ?? 0)} created · {num(result.updated ?? 0)} updated
                  {result.skipped ? ` · ${num(result.skipped)} skipped (product not found)` : ""} — the digital twin has been updated.
                </p>
              </div>
              <div className="ml-auto">
                <Button variant="outline" size="sm" onClick={reset}><ChevronLeft size={14} /> Import more data</Button>
              </div>
            </div>
          </Card>
        )}

        {/* format help */}
        <Card>
          <CardTitle className="mb-2">Accepted headers (auto-mapped)</CardTitle>
          <div className="flex items-start gap-2 text-xs leading-relaxed text-muted">
            <FileSpreadsheet size={15} className="mt-0.5 shrink-0" />
            <p>
              Headers like <em>Item Name, Product, SKU Code, MRP, Sale Price, Purchase Price, Qty, Stock, Date, Bill No</em> are
              recognized automatically — you can correct any mapping manually above. Dates accept
              <em> YYYY-MM-DD</em>, <em>DD-MM-YYYY</em> and <em>DD/MM/YYYY</em>. Amounts may include ₹ and commas.
            </p>
          </div>
        </Card>
      </motion.div>
    </AppShell>
  );
}
