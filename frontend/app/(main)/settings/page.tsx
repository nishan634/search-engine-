"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Settings } from "@/lib/types";

function Toggle({ label, help, checked, onChange }: { label: string; help: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-3">
      <input type="checkbox" className="mt-1 h-4 w-4" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span><span className="block font-medium">{label}</span><span className="muted">{help}</span></span>
    </label>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [s, setS] = useState<Settings | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => { api<Settings>("/settings/").then(setS).catch((e) => setMsg(e.message)); }, []);

  async function patch(p: Partial<Settings>) {
    setS((cur) => (cur ? { ...cur, ...p } : cur));
    try { setS(await api<Settings>("/settings/", { method: "PATCH", body: p })); setMsg("Saved."); }
    catch (e) { setMsg((e as Error).message); }
  }
  async function wipe(path: string, what: string) {
    if (!confirm(`Delete ${what}? This cannot be undone.`)) return;
    await api(path, { method: "DELETE" }); setMsg(`${what[0].toUpperCase()}${what.slice(1)} deleted.`);
  }

  if (!s) return <p className="muted">{msg || "Loading…"}</p>;
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div><h1 className="text-lg font-semibold">Settings & privacy</h1><p className="muted">{user?.email}</p></div>
      <div className="card divide-y divide-slate-200 dark:divide-slate-800">
        <Toggle label="Save search history" help="When off, new searches are not recorded at all (this also empties Insights)." checked={s.save_search_history} onChange={(v) => patch({ save_search_history: v })} />
        <Toggle label="AI memory" help="Keep chat conversations so follow-ups work across sessions. When off, chats are stateless and nothing is stored." checked={s.ai_memory_enabled} onChange={(v) => patch({ ai_memory_enabled: v })} />
        <Toggle label="AI answers use the web" help="Send your question to the web search provider when generating answers." checked={s.ai_use_web} onChange={(v) => patch({ ai_use_web: v })} />
        <Toggle label="AI answers use my library" help="Retrieve passages from your private notes and documents." checked={s.ai_use_personal} onChange={(v) => patch({ ai_use_personal: v })} />
        <div className="flex items-center gap-3 py-3">
          <span className="flex-1 font-medium">Default search mode</span>
          <select value={s.default_search_mode} onChange={(e) => patch({ default_search_mode: e.target.value as Settings["default_search_mode"] })}>
            <option value="ai">AI answer</option><option value="web">Web</option><option value="personal">My library</option>
          </select>
        </div>
      </div>
      <div className="card space-y-2">
        <h2 className="font-medium">AI and programming</h2>
        <p className="muted">
          Dada Search can use a local Ollama model or an OpenAI-compatible endpoint. Set
          <code className="mx-1 rounded bg-slate-100 px-1 dark:bg-slate-800">OPENAI_BASE_URL</code>
          and
          <code className="mx-1 rounded bg-slate-100 px-1 dark:bg-slate-800">LLM_MODEL</code>
          in <code>.env</code>. For OpenAI, also set <code>OPENAI_API_KEY</code>.
        </p>
      </div>
      <div className="card space-y-3">
        <h2 className="font-medium">Your data</h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={() => wipe("/search/history/", "all search history")}>Clear search history</button>
          <button className="btn-ghost" onClick={() => wipe("/ai/memory/", "all AI conversations")}>Clear AI memory</button>
        </div>
      </div>
      <p className="muted" aria-live="polite">{msg}</p>
    </div>
  );
}
