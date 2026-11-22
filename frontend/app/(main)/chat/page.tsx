"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnswerText, CitationList } from "@/components/Citations";
import { api } from "@/lib/api";
import type { AIAnswer, Conversation, Message, Page } from "@/lib/types";

function ChatInner() {
  const params = useSearchParams();
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(params.get("q") || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  const loadList = useCallback(async () => setConvos((await api<Page<Conversation>>("/ai/conversations/")).results), []);
  useEffect(() => { loadList().catch(() => {}); }, [loadList]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  async function open(id: number) {
    setActive(id);
    setMessages((await api<{ messages: Message[] }>(`/ai/conversations/${id}/`)).messages);
  }
  function fresh() { setActive(null); setMessages([]); setInput(""); }

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput(""); setError(""); setBusy(true);
    setMessages((m) => [...m, { id: -Date.now(), role: "user", content: text, citations: [] }]);
    try {
      const r = await api<AIAnswer>("/ai/chat/", { body: { message: text, conversation_id: active } });
      setMessages((m) => [...m, { id: -Date.now() - 1, role: "assistant", content: r.answer, citations: r.citations }]);
      if (r.conversation_id && r.conversation_id !== active) { setActive(r.conversation_id); loadList(); }
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-4 md:grid-cols-[16rem,1fr]">
      <aside className="space-y-2">
        <button className="btn w-full" onClick={fresh}>+ New chat</button>
        <ul className="space-y-1">
          {convos.map((c) => (
            <li key={c.id} className="flex items-center gap-1">
              <button onClick={() => open(c.id)} className={`flex-1 truncate rounded-lg px-3 py-2 text-left text-sm ${active === c.id ? "bg-indigo-100 dark:bg-indigo-950" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}>{c.title || "Untitled"}</button>
              <button className="px-2 text-slate-400 hover:text-red-600" aria-label="Delete conversation"
                onClick={async () => { await api(`/ai/conversations/${c.id}/`, { method: "DELETE" }); if (active === c.id) fresh(); loadList(); }}>✕</button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-h-[60vh] flex-col">
        <div className="flex-1 space-y-4">
          {messages.length === 0 && (
            <div className="space-y-3">
              <p className="muted">Ask questions, write code, debug errors, explain concepts, or use the web and your private library.</p>
              <div className="flex flex-wrap gap-2">
                {[
                  "Write a Python function that reverses a string",
                  "Explain recursion with a JavaScript example",
                  "Debug this code and suggest fixes",
                  "Create a React component for a search bar",
                ].map((prompt) => (
                  <button key={prompt} type="button" onClick={() => setInput(prompt)}
                    className="rounded-full border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "ml-auto max-w-[85%] rounded-2xl bg-indigo-600 px-4 py-2 text-white" : "card"}>
              {m.role === "user" ? <p className="whitespace-pre-wrap">{m.content}</p> : (<>
                <AnswerText text={m.content} prefix={`m${m.id}`} />
                <CitationList citations={m.citations} prefix={`m${m.id}`} />
              </>)}
            </div>
          ))}
          {busy && <p className="muted">Thinking…</p>}
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <div ref={bottom} />
        </div>
        <form onSubmit={send} className="sticky bottom-0 mt-4 flex gap-2 bg-slate-50 py-3 dark:bg-slate-950">
          <textarea className="w-full resize-y" rows={2} placeholder="Ask a question, paste code, or describe a programming problem…" value={input} onChange={(e) => setInput(e.target.value)} aria-label="Message" />
          <button className="btn" disabled={busy}>Send</button>
        </form>
      </section>
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={null}><ChatInner /></Suspense>;
}
