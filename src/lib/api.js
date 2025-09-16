// Small API helper that reads Vite env and wraps fetch with JSON helpers
const BASE = import.meta.env.VITE_API_BASE?.replace(/\/+$/, "") || "";

async function jfetch(path, opts = {}) {
  const url = path.startsWith("http") ? path : `${BASE}${path}`;
  const headers = {"Accept":"application/json", ...(opts.headers || {})};
  const res = await fetch(url, {...opts, headers});
  if (!res.ok) {
    const text = await res.text().catch(()=> "");
    throw new Error(`${res.status} ${res.statusText} :: ${text}`);
  }
  // try json, fallback text
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}
export const api = {
  // presign for a single file
  presign: ({filename, content_type}) =>
    jfetch("/api/rag/upload_url", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ filename, content_type })
    }),

  // confirm upload so backend indexes later
  confirm: ({s3_uri, title, external_id, content}) =>
    jfetch("/api/rag/confirm_upload", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ s3_uri, title, external_id, content })
    }),

  // crawl a URL
  indexUrl: ({url, title, external_id}) =>
    jfetch("/api/rag/index_url", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ url, title, external_id })
    }),
};
