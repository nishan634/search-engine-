// Access token lives in memory only. The refresh token is an httpOnly cookie managed by the backend,
// so JavaScript (and therefore XSS) can never read it.
let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) { super(message); }
}

export function setAccessToken(t: string | null) { accessToken = t; }

export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = fetch("/api/auth/refresh/", { method: "POST", credentials: "include" })
      .then(async (r) => (r.ok ? ((await r.json()).access as string) : null))
      .catch(() => null)
      .finally(() => { refreshing = null; });
  }
  const t = await refreshing;
  accessToken = t;
  return t;
}

function messageFrom(data: any, status: number): string {
  if (!data) return `Request failed (${status})`;
  if (typeof data.detail === "string") return data.detail;
  const first = Object.entries(data)[0];
  if (first) {
    const [k, v] = first as [string, unknown];
    return `${k === "non_field_errors" ? "" : k + ": "}${Array.isArray(v) ? v.join(" ") : String(v)}`;
  }
  return `Request failed (${status})`;
}

interface Opts { method?: string; body?: unknown; form?: FormData }

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const send = (token: string | null) => {
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    let body: BodyInit | undefined;
    if (opts.form) body = opts.form;
    else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
    return fetch(`/api${path}`, { method: opts.method || (body ? "POST" : "GET"), headers, body, credentials: "include" });
  };
  let res = await send(accessToken);
  if (res.status === 401 && !path.startsWith("/auth/")) {
    const t = await refreshAccessToken();
    if (t) res = await send(t);
  }
  if (!res.ok) {
    let data: unknown;
    try { data = await res.json(); } catch { /* non-JSON error */ }
    throw new ApiError(res.status, messageFrom(data, res.status), data);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function download(path: string, filename: string) {
  let res = await fetch(`/api${path}`, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {}, credentials: "include" });
  if (res.status === 401 && (await refreshAccessToken())) {
    res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${accessToken}` }, credentials: "include" });
  }
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
