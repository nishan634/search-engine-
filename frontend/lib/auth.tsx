"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, refreshAccessToken, setAccessToken } from "./api";
import type { User } from "./types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await refreshAccessToken(); // silent sign-in from the httpOnly cookie
      if (token) {
        try { setUser(await api<User>("/auth/me/")); } catch { setAccessToken(null); }
      }
      setLoading(false);
    })();
  }, []);

  const finish = (r: { access: string; user: User }) => { setAccessToken(r.access); setUser(r.user); };
  const login = useCallback(async (email: string, password: string) =>
    finish(await api("/auth/login/", { body: { email, password } })), []);
  const register = useCallback(async (email: string, password: string, display_name: string) =>
    finish(await api("/auth/register/", { body: { email, password, display_name } })), []);
  const logout = useCallback(async () => {
    try { await api("/auth/logout/", { method: "POST" }); } finally { setAccessToken(null); setUser(null); }
  }, []);

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>;
}
