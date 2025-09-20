export const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export async function pingHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { mode: "cors" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return { ok: json?.status === "ok", json };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}
