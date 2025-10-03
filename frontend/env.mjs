// Single source of truth for the backend host.
export const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "";
// Always build API paths from BACKEND
export const API = `${BACKEND.replace(/\/+$/,"")}/api`;
