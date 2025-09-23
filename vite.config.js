import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/realtime": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: false,
      },
      "/session": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});











