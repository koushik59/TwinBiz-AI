"use client";

import { inr, num, shortDate } from "@/lib/utils";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/* Palette roles are read from CSS vars so light/dark stays validated */
export const SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
];

const AXIS = { stroke: "var(--grid)", fontSize: 11, fill: "var(--muted)" } as const;

function tooltipStyle() {
  return {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    fontSize: 12,
    color: "var(--ink)",
    boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
  };
}

type Row = Record<string, unknown>;

export function TrendArea({
  data,
  x,
  series,
  height = 280,
  money = true,
}: {
  data: Row[];
  x: string;
  series: { key: string; label: string }[];
  height?: number;
  money?: boolean;
}) {
  const fmt = money ? inr : num;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          {series.map((s, i) => (
            <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SERIES[i]} stopOpacity={0.28} />
              <stop offset="100%" stopColor={SERIES[i]} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 6" stroke="var(--grid)" vertical={false} />
        <XAxis dataKey={x} tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--grid)" }} tickFormatter={(v) => shortDate(String(v))} minTickGap={40} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(Number(v))} width={56} />
        <Tooltip
          contentStyle={tooltipStyle()}
          labelFormatter={(v) => shortDate(String(v))}
          formatter={(value, name) => [fmt(Number(value)), String(name)]}
        />
        {series.length > 1 && <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />}
        {series.map((s, i) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={SERIES[i]}
            strokeWidth={2}
            fill={`url(#grad-${s.key})`}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
            animationDuration={800}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function TrendLines({
  data,
  x,
  series,
  height = 280,
  money = true,
  xIsDate = true,
}: {
  data: Row[];
  x: string;
  series: { key: string; label: string }[];
  height?: number;
  money?: boolean;
  xIsDate?: boolean;
}) {
  const fmt = money ? inr : num;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 6" stroke="var(--grid)" vertical={false} />
        <XAxis dataKey={x} tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--grid)" }} tickFormatter={(v) => (xIsDate ? shortDate(String(v)) : String(v))} minTickGap={40} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(Number(v))} width={56} />
        <Tooltip contentStyle={tooltipStyle()} labelFormatter={(v) => (xIsDate ? shortDate(String(v)) : String(v))} formatter={(value, name) => [fmt(Number(value)), String(name)]} />
        {series.length > 1 && <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />}
        {series.map((s, i) => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={SERIES[i]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} animationDuration={800} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function SimpleBars({
  data,
  x,
  y,
  label,
  height = 260,
  money = true,
  horizontal = false,
}: {
  data: Row[];
  x: string;
  y: string;
  label: string;
  height?: number;
  money?: boolean;
  horizontal?: boolean;
}) {
  const fmt = money ? inr : num;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 8, right: 8, left: horizontal ? 30 : 0, bottom: 0 }} barCategoryGap="28%">
        <CartesianGrid strokeDasharray="3 6" stroke="var(--grid)" horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(Number(v))} />
            <YAxis type="category" dataKey={x} tick={{ ...AXIS, fontSize: 11 }} tickLine={false} axisLine={false} width={110} />
          </>
        ) : (
          <>
            <XAxis dataKey={x} tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--grid)" }} minTickGap={10} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(Number(v))} width={56} />
          </>
        )}
        <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: "var(--brand-soft)" }} formatter={(value) => [fmt(Number(value)), label]} />
        <Bar dataKey={y} name={label} fill="var(--series-1)" radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} animationDuration={800} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({ data, height = 240 }: { data: { name: string; value: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="85%" paddingAngle={2} stroke="var(--surface)" strokeWidth={2} animationDuration={800}>
          {data.map((_, i) => (
            <Cell key={i} fill={SERIES[i % SERIES.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle()} formatter={(value, name) => [inr(Number(value)), String(name)]} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/** Forecast chart: history line + prediction line + confidence band */
export function ForecastChart({
  history,
  forecast,
  height = 300,
  money = true,
}: {
  history: { day: string; value: number }[];
  forecast: { day: string; value: number; low: number; high: number }[];
  height?: number;
  money?: boolean;
}) {
  const fmt = money ? inr : num;
  const data: Row[] = [
    ...history.map((h) => ({ day: h.day, actual: h.value })),
    ...forecast.map((f) => ({ day: f.day, predicted: f.value, low: f.low, band: f.high - f.low })),
  ];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 6" stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--grid)" }} tickFormatter={(v) => shortDate(String(v))} minTickGap={40} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(Number(v))} width={56} />
        <Tooltip
          contentStyle={tooltipStyle()}
          labelFormatter={(v) => shortDate(String(v))}
          formatter={(value, name) => [fmt(Number(value)), name === "actual" ? "Actual" : name === "predicted" ? "Predicted" : String(name)]}
        />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />
        {/* invisible base + band = confidence interval */}
        <Area dataKey="low" stackId="ci" stroke="none" fill="transparent" legendType="none" tooltipType="none" animationDuration={0} />
        <Area dataKey="band" stackId="ci" stroke="none" fill="var(--series-5)" fillOpacity={0.14} name="Confidence band" legendType="none" animationDuration={800} />
        <Area dataKey="actual" name="Actual" stroke="var(--series-1)" strokeWidth={2} fill="transparent" dot={false} animationDuration={800} />
        <Area dataKey="predicted" name="Predicted" stroke="var(--series-5)" strokeWidth={2} strokeDasharray="6 4" fill="transparent" dot={false} animationDuration={800} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
