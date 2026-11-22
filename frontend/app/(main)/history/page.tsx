"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HistoryEntry, Page } from "@/lib/types";

export default function HistoryPage() {
  const [rows, setRows] = useState<HistoryEntry[]>([]);
  const [mode, setMode] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setRows((await api<Page<HistoryEntry>>(`/search/history/${mode ? `?mode=${mode}` : ""}`)).results);
  }, [mode]);
  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);

  async function clear() {
    if (!confirm("Delete your entire search history?")) return;
    await api("/search/history/", { method: "DELETE" }); load();
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h1 className="text-lg font-semibold">Search history</h1>
        <select className="ml-auto" value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Filter by mode">
          <option value="">All modes</option><option value="web">Web</option><option value="personal">Library</option><option value="ai">AI</option>
        </select>
        <button className="btn-ghost" onClick={clear} disabled={!rows.length}>Clear all</button>
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {rows.length === 0 && <p className="muted">No history. (You can turn history off in Settings.)</p>}
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.id} className="card flex items-center gap-3">
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">{r.mode}</span>
            <Link href={`/?q=${encodeURIComponent(r.query)}&mode=${r.mode}`} className="flex-1 truncate hover:underline">{r.query}</Link>
            <span className="muted hidden sm:inline">{r.result_count} results · {new Date(r.created_at).toLocaleString()}</span>
            <button className="btn-ghost" aria-label="Delete entry" onClick={async () => { await api(`/search/history/${r.id}/`, { method: "DELETE" }); load(); }}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
