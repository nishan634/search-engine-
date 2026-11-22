"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, download } from "@/lib/api";
import type { Collection, Item, Page } from "@/lib/types";

const BADGE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  ready: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};
const ICON: Record<string, string> = { note: "📝", bookmark: "🔖", document: "📄" };

function LibraryInner() {
  const params = useSearchParams();
  const [items, setItems] = useState<Item[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [kind, setKind] = useState("");
  const [tab, setTab] = useState<"note" | "url" | "file">("note");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [tags, setTags] = useState("");
  const [collectionId, setCollectionId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<(Item & { content: string }) | null>(null);
  const [summary, setSummary] = useState("");

  const load = useCallback(async () => {
    const r = await api<Page<Item>>(`/knowledge/${kind ? `?kind=${kind}` : ""}`);
    setItems(r.results);
  }, [kind]);

  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);
  useEffect(() => { api<Collection[]>("/collections/").then(setCollections).catch(() => {}); }, []);
  // poll while anything is still being processed in the background
  useEffect(() => {
    if (!items.some((i) => i.status === "pending")) return;
    const t = setInterval(() => load().catch(() => {}), 2500);
    return () => clearInterval(t);
  }, [items, load]);
  useEffect(() => { const id = params.get("open"); if (id) view(Number(id)); /* eslint-disable-next-line */ }, []);

  async function view(id: number) {
    setSummary("");
    setOpen(await api(`/knowledge/${id}/`));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    const org = { tags: tags.split(",").map((t) => t.trim()).filter(Boolean), ...(collectionId && { collection_ids: [Number(collectionId)] }) };
    try {
      if (tab === "file") {
        if (!file) throw new Error("Choose a file.");
        const f = new FormData();
        f.append("file", file);
        if (title) f.append("title", title);
        org.tags.forEach((t) => f.append("tags", t));
        if (collectionId) f.append("collection_ids", collectionId);
        await api("/knowledge/upload/", { form: f });
      } else if (tab === "url") {
        await api("/knowledge/save/", { body: { url, title, ...org } });
      } else {
        await api("/knowledge/save/", { body: { title, content, ...org } });
      }
      setTitle(""); setContent(""); setUrl(""); setFile(null); setTags("");
      await load();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  async function remove(id: number) {
    if (!confirm("Delete this item permanently?")) return;
    await api(`/knowledge/${id}/`, { method: "DELETE" });
    setOpen(null); load();
  }

  async function summarize(id: number) {
    setSummary("Summarizing…");
    try { setSummary((await api<{ summary: string }>("/ai/summarize/", { body: { item_id: id, style: "bullets" } })).summary); }
    catch (e) { setSummary((e as Error).message); }
  }

  return (
    <div className="grid gap-6 md:grid-cols-[22rem,1fr]">
      <form onSubmit={submit} className="card h-fit space-y-3">
        <div className="flex gap-1" role="tablist">
          {(["note", "url", "file"] as const).map((t) => (
            <button type="button" key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`flex-1 rounded-lg px-2 py-1.5 text-sm ${tab === t ? "bg-indigo-600 text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}>
              {t === "note" ? "Note" : t === "url" ? "Website" : "Upload"}
            </button>
          ))}
        </div>
        {tab !== "url" && <input className="w-full" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} required={tab === "note"} />}
        {tab === "note" && <textarea className="h-32 w-full" placeholder="Write your note…" value={content} onChange={(e) => setContent(e.target.value)} required />}
        {tab === "url" && <input className="w-full" type="url" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} required />}
        {tab === "file" && <input className="w-full" type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] || null)} required />}
        <input className="w-full" placeholder="Tags (comma separated)" value={tags} onChange={(e) => setTags(e.target.value)} />
        <select className="w-full" value={collectionId} onChange={(e) => setCollectionId(e.target.value)} aria-label="Collection">
          <option value="">No collection</option>
          {collections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button className="btn w-full" disabled={busy}>{busy ? "Saving…" : tab === "file" ? "Upload & index" : "Save & index"}</button>
        <p className="muted">PDF, DOCX, TXT and MD up to 25 MB. Content is private to your account.</p>
      </form>

      <div>
        <div className="mb-3 flex items-center gap-2">
          <h1 className="text-lg font-semibold">Library</h1>
          <select className="ml-auto" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Filter by type">
            <option value="">All</option><option value="note">Notes</option><option value="bookmark">Bookmarks</option><option value="document">Documents</option>
          </select>
        </div>
        {items.length === 0 && <p className="muted">Nothing here yet. Save a note, a website or a document.</p>}
        <ul className="space-y-2">
          {items.map((i) => (
            <li key={i.id} className="card flex items-start gap-3">
              <span aria-hidden>{ICON[i.kind]}</span>
              <div className="min-w-0 flex-1">
                <button className="truncate text-left font-medium hover:underline" onClick={() => view(i.id)}>{i.title}</button>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs ${BADGE[i.status]}`}>{i.status}</span>
                  {i.tags.map((t) => <span key={t} className="muted">#{t}</span>)}
                  {i.error && <span className="text-xs text-red-600">{i.error}</span>}
                </div>
                {i.snippet && <p className="muted mt-1 line-clamp-2">{i.snippet}</p>}
              </div>
              <button className="btn-ghost" onClick={() => remove(i.id)} aria-label={`Delete ${i.title}`}>🗑</button>
            </li>
          ))}
        </ul>
      </div>

      {open && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/50 p-4" onClick={() => setOpen(null)}>
          <div className="card max-h-[85vh] w-full max-w-2xl overflow-y-auto" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal>
            <div className="flex items-start gap-2">
              <h2 className="flex-1 text-lg font-semibold">{open.title}</h2>
              <button className="btn-ghost" onClick={() => setOpen(null)}>Close</button>
            </div>
            {open.url && <a href={open.url} target="_blank" rel="noopener noreferrer" className="text-sm text-indigo-600 hover:underline">{open.url}</a>}
            <div className="my-3 flex gap-2">
              <button className="btn-ghost" onClick={() => summarize(open.id)}>✨ Summarize</button>
              {open.kind === "document" && <button className="btn-ghost" onClick={() => download(`/knowledge/${open.id}/download/`, open.original_name || "document")}>Download original</button>}
            </div>
            {summary && <div className="card mb-3 whitespace-pre-wrap bg-indigo-50 text-sm dark:bg-indigo-950/40">{summary}</div>}
            <pre className="whitespace-pre-wrap break-words text-sm">{open.content.slice(0, 20000) || "(no text yet)"}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={null}><LibraryInner /></Suspense>;
}
