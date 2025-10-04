import { defineConfig } from "vite";

// Local dev helper: proxy /api/* to a local FastAPI (optional)
const LOCAL_BACKEND = process.env.LOCAL_BACKEND || "http://localhost:8000";

export default defineConfig({
  server: {
    proxy: {
      // This is ONLY used during `npm run dev` if you choose to hit relative /api/*
      "/api": {
        target: LOCAL_BACKEND,
        changeOrigin: true,
      },
    },
  },
});








