"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "Search" },
  { href: "/chat/", label: "Chat" },
  { href: "/library/", label: "Library" },
  { href: "/collections/", label: "Collections" },
  { href: "/history/", label: "History" },
  { href: "/insights/", label: "Insights" },
  { href: "/settings/", label: "Settings" },
];

export default function Nav() {
  const path = usePathname();
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
        <Link href="/" className="shrink-0 text-lg font-semibold">🔎 Dada Search</Link>
        <nav className="flex flex-1 gap-1 overflow-x-auto" aria-label="Main">
          {links.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link key={l.href} href={l.href}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${active
                  ? "bg-indigo-100 font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}>
                {l.label}
              </Link>
            );
          })}
        </nav>
        <button onClick={logout} className="btn-ghost shrink-0" title={user?.email}>Sign out</button>
      </div>
    </header>
  );
}
