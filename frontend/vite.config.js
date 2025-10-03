// frontend/vite.config.js
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    // Local dev only: proxy /api/* to your local FastAPI on 8000
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});








