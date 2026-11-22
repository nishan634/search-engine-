"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Collection, Item, Page } from "@/lib/types";

export default function CollectionsPage() {
  const [cols, setCols] = useState<Collection[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [active, setActive] = useState<Collection | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => api<Collection[]>("/collections/").then(setCols), []);
  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await api("/collections/", { body: { name, description: desc } }); setName(""); setDesc(""); load(); }
    catch (err) { setError((err as Error).message); }
  }
  async function open(c: Collection) {
    setActive(c);
    setItems((await api<Page<Item>>(`/knowledge/?collection=${c.id}`)).results);
  }
  async function remove(c: Collection) {
    if (!confirm(`Delete collection "${c.name}"? Items in it are kept.`)) return;
    await api(`/collections/${c.id}/`, { method: "DELETE" });
    if (active?.id === c.id) setActive(null);
    load();
  }

  return (
    <div className="grid gap-6 md:grid-cols-[20rem,1fr]">
      <div className="space-y-4">
        <form onSubmit={create} className="card space-y-2">
          <h2 className="font-medium">New collection</h2>
          <input className="w-full" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input className="w-full" placeholder="Description (optional)" value={desc} onChange={(e) => setDesc(e.target.value)} />
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <button className="btn w-full">Create</button>
        </form>
        <ul className="space-y-2">
          {cols.map((c) => (
            <li key={c.id} className={`card flex items-center gap-2 ${active?.id === c.id ? "ring-2 ring-indigo-500" : ""}`}>
              <button className="flex-1 text-left" onClick={() => open(c)}>
                <div className="font-medium">{c.name}</div>
                <div className="muted">{c.item_count} item{c.item_count === 1 ? "" : "s"}</div>
              </button>
              <button className="btn-ghost" onClick={() => remove(c)} aria-label={`Delete ${c.name}`}>🗑</button>
            </li>
          ))}
          {cols.length === 0 && <li className="muted">No collections yet.</li>}
        </ul>
      </div>
      <div>
        {active ? (<>
          <h1 className="mb-1 text-lg font-semibold">{active.name}</h1>
          {active.description && <p className="muted mb-3">{active.description}</p>}
          <ul className="space-y-2">
            {items.map((i) => (
              <li key={i.id} className="card"><div className="font-medium">{i.title}</div><p className="muted line-clamp-2">{i.snippet}</p></li>
            ))}
            {items.length === 0 && <li className="muted">Empty. Assign items to this collection when saving them in Library.</li>}
          </ul>
        </>) : <p className="muted">Select a collection to see what's inside.</p>}
      </div>
    </div>
  );
}
