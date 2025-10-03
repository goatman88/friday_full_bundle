import { defineConfig } from "vite";

export default defineConfig({
  server: {
    // local dev only: point /api/* to your local FastAPI (change port if needed)
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});







