import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // Force an empty PostCSS config so Vite doesn't try to find/parse any config
  css: { postcss: { plugins: [] } },

  plugins: [react()],

  // Not required on Render, but safe to keep:
  server:  { host: "0.0.0.0", port: 5173 },
  preview: { host: "0.0.0.0", port: 5173 },
});

