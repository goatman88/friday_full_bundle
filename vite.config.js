import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Use VITE_API_BASE for production builds if you deploy static assets somewhere else.
// During local dev, proxy /api to your Render app or local backend as needed.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "https://friday-099e.onrender.com";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        secure: true
      }
    }
  },
  // Important: don't add extra HTML inputs here; let Vite use root ./index.html
});
