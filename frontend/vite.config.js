import { defineConfig } from "vite";

// In local dev we want /api/* -> http://localhost:8000
// In production (Render/static) this proxy is ignored; main.js uses absolute URL when VITE_BACKEND_URL is set.
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});


