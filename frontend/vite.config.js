import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "h",
        changeOrigin: true,
        secure: true
      }
    }
  },
});
