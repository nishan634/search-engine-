"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Insights } from "@/lib/types";

function Bars({ data }: { data: [string, number][] }) {
  const max = Math.max(1, ...data.map((d) => d[1]));
  return (
    <ul className="space-y-1.5">
      {data.map(([k, v]) => (
        <li key={k} className="flex items-center gap-2 text-sm">
          <span className="w-28 shrink-0 truncate">{k}</span>
          <span className="h-3 rounded bg-indigo-500" style={{ width: `${(v / max) * 100}%`, minWidth: 4 }} />
          <span className="muted">{v}</span>
        </li>
      ))}
    </ul>
  );
}

export default function InsightsPage() {
  const [d, setD] = useState<Insights | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Insights>("/analytics/summary/?days=30").then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <p role="alert" className="text-sm text-red-600">{error}</p>;
  if (!d) return <p className="muted">Loading…</p>;
  const total = Object.values(d.searches_by_mode).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Your search insights <span className="muted">(last {d.period_days} days)</span></h1>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card"><div className="text-3xl font-semibold">{total}</div><div className="muted">searches</div></div>
        <div className="card"><div className="text-3xl font-semibold">{Object.values(d.library).reduce((a, b) => a + b, 0)}</div><div className="muted">library items</div></div>
        <div className="card"><div className="text-3xl font-semibold">{d.conversations}</div><div className="muted">AI conversations</div></div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card"><h2 className="mb-2 font-medium">By mode</h2>{total ? <Bars data={Object.entries(d.searches_by_mode)} /> : <p className="muted">No searches recorded.</p>}</div>
        <div className="card"><h2 className="mb-2 font-medium">Library</h2>{Object.keys(d.library).length ? <Bars data={Object.entries(d.library)} /> : <p className="muted">Library is empty.</p>}</div>
        <div className="card"><h2 className="mb-2 font-medium">Top queries</h2>
          {d.top_queries.length ? <Bars data={d.top_queries.map((q) => [q.query, q.count])} /> : <p className="muted">—</p>}</div>
        <div className="card"><h2 className="mb-2 font-medium">Searches per day</h2>
          {d.searches_per_day.length ? <Bars data={d.searches_per_day.map((x) => [x.date, x.count])} /> : <p className="muted">—</p>}</div>
      </div>
    </div>
  );
}
