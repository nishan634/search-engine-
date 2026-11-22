"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

export default function Page() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = false as boolean;

  useEffect(() => { if (!loading && user) router.replace("/"); }, [loading, user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      if (isLogin) await login(email, password); else await register(email, password, name);
      router.replace("/");
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto mt-24 w-full max-w-sm px-4">
      <h1 className="mb-1 text-2xl font-semibold">🔎 Dada Search</h1>
      <p className="muted mb-6">Your private, AI-powered search engine.</p>
      <form onSubmit={submit} className="card space-y-3">
        <h2 className="font-medium">Create account</h2>
        {!isLogin && <input className="w-full" placeholder="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} />}
        <input className="w-full" type="email" required autoComplete="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full" type="password" required minLength={isLogin ? 1 : 10} autoComplete={isLogin ? "current-password" : "new-password"}
          placeholder={isLogin ? "Password" : "Password (min 10 characters)"} value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button className="btn w-full" disabled={busy}>{busy ? "Please wait…" : "Create account"}</button>
        <p className="muted text-center">Already registered? <Link className="text-indigo-600 hover:underline" href="/login/">Sign in</Link></p>
      </form>
    </div>
  );
}
