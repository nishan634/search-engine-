import type { Citation } from "@/lib/types";
import Link from "next/link";

export function AnswerText({ text, prefix = "src" }: { text: string; prefix?: string }) {
  const blocks = text.split(/(```[\s\S]*?```)/g);
  return (
    <div className="space-y-3 leading-relaxed">
      {blocks.map((block, blockIndex) => {
        if (block.startsWith("```")) {
          const match = block.match(/^```([\w-]*)\n?([\s\S]*?)```$/);
          if (match) {
            return (
              <pre key={blockIndex} className="overflow-x-auto rounded-lg bg-slate-950 p-4 text-sm text-slate-100">
                {match[1] && <code className="block mb-2 text-xs text-slate-400">{match[1]}</code>}
                <code>{match[2].replace(/\n$/, "")}</code>
              </pre>
            );
          }
        }
        const parts = block.split(/(\[\d+\])/g);
        return (
          <p key={blockIndex} className="whitespace-pre-wrap">
            {parts.map((p, i) => {
              const m = p.match(/^\[(\d+)\]$/);
              return m ? (
                <a key={i} href={`#${prefix}-${m[1]}`} className="mx-0.5 align-super text-xs font-semibold text-indigo-600 hover:underline dark:text-indigo-400">[{m[1]}]</a>
              ) : <span key={i}>{p}</span>;
            })}
          </p>
        );
      })}
    </div>
  );
}

export function CitationList({ citations, prefix = "src" }: { citations: Citation[]; prefix?: string }) {
  if (!citations.length) return null;
  return (
    <ol className="mt-4 space-y-2">
      {citations.map((c) => (
        <li key={c.index} id={`${prefix}-${c.index}`} className={`card scroll-mt-20 ${c.cited ? "" : "opacity-60"}`}>
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold">[{c.index}]</span>
            <span className={`rounded px-1.5 py-0.5 text-xs ${c.type === "web"
              ? "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300"
              : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"}`}>
              {c.type === "web" ? "Web" : "My library"}
            </span>
            {c.url ? (
              <a href={c.url} target="_blank" rel="noopener noreferrer" className="truncate font-medium hover:underline">{c.title}</a>
            ) : c.item_id ? (
              <Link href={`/library/?open=${c.item_id}`} className="truncate font-medium hover:underline">{c.title}</Link>
            ) : <span className="truncate font-medium">{c.title}</span>}
          </div>
          {c.url && <div className="truncate text-xs text-slate-500">{c.url}</div>}
          <p className="muted mt-1 line-clamp-3">{c.snippet}</p>
        </li>
      ))}
    </ol>
  );
}
