// Single source of truth for the backend base URL
export const BACKEND = import.meta.env.VITE_BACKEND_URL;
export const api = (path) => new URL(path, BACKEND).toString();

