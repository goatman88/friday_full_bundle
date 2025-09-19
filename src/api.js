// Simple client for Friday backend.
// Figures out the API base from env, or falls back to same-origin /api.

const envBase = import.meta.env?.VITE_API_BASE?.trim();
const defaultBase =
  (typeof window !== "undefined" && `${window.location.origin}/api`) ||
  "http://localhost:8000/api";

export const API_BASE = envBase || defaultBase;

async function ok(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} – ${text}`.trim());
  }
  return res;
}

export async function health() {
  const r = await ok(fetch(`${API_BASE}/health`));
  return r.json();
}

// === RAG ingest/upload ===

export async function requestUploadUrl() {
  const r = await ok(fetch(`${API_BASE}/rag/upload_url`, { method: "POST" }));
  return r.json(); // { token, put_url }
}

// PUT raw bytes to the pre-signed URL (or echo URL)
export async function putToUrl(putUrl, bytes, contentType = "text/plain") {
  const r = await ok(
    fetch(putUrl, {
      method: "PUT",
      headers: { "Content-Type": contentType },
      body: bytes,
    })
  );
  return r.ok;
}

// Confirm the upload and ask backend to chunk & index
export async function confirmUpload({
  token,
  collection = "default",
  chunk_size = 800,
  overlap = 120,
  index = "both", // "faiss" | "s3" | "both"
}) {
  const r = await ok(
    fetch(`${API_BASE}/rag/confirm_upload`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, collection, chunk_size, overlap, index }),
    })
  );
  return r.json(); // { indexed, chunks, collection, index }
}

// Query
export async function queryRag({ q, top_k = 5, index = "both" }) {
  const r = await ok(
    fetch(`${API_BASE}/rag/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q, top_k, index }),
    })
  );
  return r.json(); // { answer, hits }
}
