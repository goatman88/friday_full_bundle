// Single source of truth for the backend host.
// At build time on Render, VITE_BACKEND_URL is baked into the bundle.
export const BACKEND = (import.meta?.env?.VITE_BACKEND_URL || "").trim().replace(/\/+$/, "");

if (!BACKEND) {
  // Helpful message in local dev if you forgot .env.local
  // (Site will still run; fetches will fail until you set this.)
  console.warn("VITE_BACKEND_URL is empty. Set it in frontend/.env.local (local dev) or Render env (deploy).");
}

// Build a full URL to the backend for /api/* endpoints
export function api(path) {
  const p = String(path || "").startsWith("/") ? path : `/${path}`;
  return `${BACKEND}${p}`;
}

