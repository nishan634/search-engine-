"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { AnswerText, CitationList } from "@/components/Citations";
import { api } from "@/lib/api";
import type { AIAnswer, Item, Mode, PersonalResult, Settings, WebResult } from "@/lib/types";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "ai", label: "AI answer", hint: "Cited answer from the web and your library" },
  { id: "web", label: "Web", hint: "Search the public internet" },
  { id: "personal", label: "My library", hint: "Search your notes, bookmarks and documents" },
];
const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "images", label: "Images" },
  { id: "news", label: "News" },
  { id: "videos", label: "Videos" },
  { id: "maps", label: "Maps" },
  { id: "shopping", label: "Shopping" },
] as const;

function SearchInner() {
  const params = useSearchParams();
  const [mode, setMode] = useState<Mode>((params.get("mode") as Mode) || "ai");
  const [q, setQ] = useState(params.get("q") || "");
  const [useWeb, setUseWeb] = useState(true);
  const [usePersonal, setUsePersonal] = useState(true);
  const [timeRange, setTimeRange] = useState("");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]["id"]>("all");
  const [kind, setKind] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [web, setWeb] = useState<WebResult[] | null>(null);
  const [personal, setPersonal] = useState<PersonalResult[] | null>(null);
  const [ai, setAi] = useState<AIAnswer | null>(null);
  const [sugg, setSugg] = useState<{ text: string; source: string }[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    api<Settings>("/settings/").then((s) => {
      if (!params.get("mode")) setMode(s.default_search_mode);
      setUseWeb(s.ai_use_web); setUsePersonal(s.ai_use_personal);
    }).catch(() => {});
    if (params.get("q")) run(params.get("q")!, (params.get("mode") as Mode) || undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onInput(v: string) {
    setQ(v);
    clearTimeout(timer.current);
    if (v.trim().length < 2) return setSugg([]);
    timer.current = setTimeout(() => {
      api<{ suggestions: { text: string; source: string }[] }>(`/search/suggestions/?q=${encodeURIComponent(v)}`)
        .then((r) => setSugg(r.suggestions)).catch(() => {});
    }, 200);
  }

  async function run(query = q, m: Mode = mode) {
    if (!query.trim()) return;
    setBusy(true); setError(""); setSugg([]); setWeb(null); setPersonal(null); setAi(null);
    try {
      if (m === "web") {
        const r = await api<{ results: WebResult[] }>("/search/web/", {
          body: { query, category, ...(timeRange && { time_range: timeRange }) },
        });
        setWeb(r.results);
      } else if (m === "personal") {
        const r = await api<{ results: PersonalResult[] }>("/search/personal/", { body: { query, ...(kind && { kind }) } });
        setPersonal(r.results);
      } else {
        setAi(await api<AIAnswer>("/search/ai/", { body: { question: query, use_web: useWeb, use_personal: usePersonal } }));
      }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2" role="tablist">
        {MODES.map((m) => (
          <button key={m.id} role="tab" aria-selected={mode === m.id} title={m.hint} onClick={() => setMode(m.id)}
            className={`rounded-full px-4 py-1.5 text-sm ${mode === m.id ? "bg-indigo-600 text-white" : "border border-slate-300 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"}`}>
            {m.label}
          </button>
        ))}
      </div>

      {mode === "web" && (
        <div className="mb-3 flex flex-wrap gap-2" aria-label="Search categories">
          {CATEGORIES.map((item) => (
            <button key={item.id} type="button" onClick={() => setCategory(item.id)}
              className={`rounded-full px-3 py-1 text-xs ${category === item.id
                ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                : "border border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}>
              {item.label}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); run(); }} className="relative">
        <div className="flex gap-2">
          <input className="w-full !py-3 text-base" placeholder={MODES.find((m) => m.id === mode)!.hint + "…"} value={q}
            onChange={(e) => onInput(e.target.value)} aria-label="Search" autoFocus />
          <button className="btn px-6" disabled={busy}>{busy ? "…" : "Search"}</button>
        </div>
        {sugg.length > 0 && (
          <ul className="card absolute z-10 mt-1 w-full max-w-[calc(100%-6rem)] !p-1">
            {sugg.map((s, i) => (
              <li key={i}><button type="button" className="flex w-full justify-between rounded px-3 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={() => { setQ(s.text); run(s.text); }}>
                <span>{s.text}</span><span className="muted">{s.source}</span></button></li>
            ))}
          </ul>
        )}
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
        {mode === "ai" && (<>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={useWeb} onChange={(e) => setUseWeb(e.target.checked)} /> Web</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={usePersonal} onChange={(e) => setUsePersonal(e.target.checked)} /> My library</label>
        </>)}
        {mode === "web" && (
          <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)} aria-label="Time range">
            <option value="">Any time</option><option value="day">Past day</option><option value="week">Past week</option>
            <option value="month">Past month</option><option value="year">Past year</option>
          </select>
        )}
        {mode === "personal" && (
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Type">
            <option value="">All types</option><option value="note">Notes</option><option value="bookmark">Bookmarks</option><option value="document">Documents</option>
          </select>
        )}
      </div>

      {error && <p role="alert" className="card mt-4 border-red-300 text-sm text-red-700 dark:text-red-400">{error}</p>}
      {busy && <p className="muted mt-6">{mode === "ai" ? "Searching and writing an answer…" : "Searching…"}</p>}

      {ai && (
        <section className="mt-6">
          <div className="card"><AnswerText text={ai.answer} />
            {ai.warnings?.map((w, i) => <p key={i} className="muted mt-2">⚠ {w}</p>)}
            <Link className="btn-ghost mt-3" href={`/chat/?q=${encodeURIComponent(q)}`}>Ask follow-ups in chat →</Link>
          </div>
          <h2 className="mt-5 text-sm font-semibold uppercase tracking-wide text-slate-500">Sources</h2>
          <CitationList citations={ai.citations} />
        </section>
      )}

      {web && (
        <ul className="mt-6 space-y-3">
          {web.length === 0 && <li className="muted">No results.</li>}
          {web.map((r, i) => (
            <li key={i} className="card">
              <a href={r.url} target="_blank" rel="noopener noreferrer" className="font-medium text-indigo-700 hover:underline dark:text-indigo-300">{r.title}</a>
              <div className="truncate text-xs text-emerald-700 dark:text-emerald-400">{r.url}</div>
              <p className="muted mt-1">{r.snippet}</p>
            </li>
          ))}
        </ul>
      )}

      {personal && (
        <ul className="mt-6 space-y-3">
          {personal.length === 0 && <li className="muted">Nothing in your library matches. Add notes, bookmarks or documents in Library.</li>}
          {personal.map((r) => (
            <li key={r.id} className="card">
              <div className="flex items-center gap-2">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">{r.kind}</span>
                <Link href={`/library/?open=${r.id}`} className="font-medium hover:underline">{r.title}</Link>
                {r.tags.map((t) => <span key={t} className="muted">#{t}</span>)}
              </div>
              {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" className="block truncate text-xs text-emerald-700 hover:underline dark:text-emerald-400">{r.url}</a>}
              <p className="muted mt-1">{r.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={null}><SearchInner /></Suspense>;
}
