import { defineConfig } from 'vite';

// During local dev, Vite proxies /api to your live backend so the same code works
const target = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  server: { proxy: {} },
  define: {
    'import.meta.env.VITE_BACKEND_URL': JSON.stringify(process.env.VITE_BACKEND_URL)
  }
});











