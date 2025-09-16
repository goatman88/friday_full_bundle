// src/lib/apiBase.ts
const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE ||
  (process as any)?.env?.NEXT_PUBLIC_API_BASE ||
  (process as any)?.env?.REACT_APP_API_BASE ||
  "";

export default API_BASE;
