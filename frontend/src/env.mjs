export const BACKEND = import.meta.env.VITE_BACKEND_URL;
export const api = (p) => new URL(p, BACKEND).toString();


