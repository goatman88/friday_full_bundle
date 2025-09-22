const BASE = import.meta.env.VITE_API_BASE?.trim();

if (!BASE) {
  console.warn("VITE_API_BASE is empty. Set it in .env");
}

export async function apiGet(path: string) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, { credentials: "omit" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function pingBoth() {
  const root = await apiGet("/health");
  const api  = await apiGet("/api/health");
  return { root, api };
}
