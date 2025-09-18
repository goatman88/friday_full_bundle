// src/api.js
const DEFAULT_BASE =
  (typeof window !== "undefined" ? window.location.origin : "") + "/api";

const API_BASE = import.meta?.env?.VITE_API_BASE?.replace(/\/+$/, "") || DEFAULT_BASE;

async function json(res) {
  const text = await res.text();
  try { return JSON.parse(text || "{}"); } catch { return { raw: text }; }
}

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health failed: ${res.status}`);
  return json(res);
}

export async function createUploadUrl() {
  const res = await fetch(`${API_BASE}/rag/upload_url`, { method: "POST" });
  if (!res.ok) throw new Error(`upload_url failed: ${res.status}`);
  return json(res); // { token, put_url }
}

export async function putBytes(putUrl, bytes, contentType = "text/plain") {
  const res = await fetch(putUrl, { method: "PUT", headers: { "Content-Type": contentType }, body: bytes });
  if (!res.ok) throw new Error(`PUT failed: ${res.status}`);
  return true;
}

export async function confirmUpload({ token, collection = "default", chunk_size = 800, overlap = 120, index = "both" }) {
  const payload = { token, collection, chunk_size, overlap, index };
  const res = await fetch(`${API_BASE}/rag/confirm_upload`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`confirm_upload failed: ${res.status}`);
  return json(res); // { indexed, chunks, collection, index }
}

export async function queryRag({ q, top_k = 5, index = "both" }) {
  const res = await fetch(`${API_BASE}/rag/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q, top_k, index }),
  });
  if (!res.ok) throw new Error(`query failed: ${res.status}`);
  return json(res); // { answer, hits }
}

export { API_BASE };
