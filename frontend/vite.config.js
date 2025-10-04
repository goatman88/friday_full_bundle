import { defineConfig } from "vite";

const LOCAL_BACKEND = "http://localhost:8000";

export default defineConfig({
  server: {
    proxy: {
      // only used if your code calls relative paths (we don’t by default)
      "/api": {
        target: process.env.VITE_BACKEND_URL || LOCAL_BACKEND,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});









