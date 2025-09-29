import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      // In dev, send /api/* to FastAPI on 8000
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

