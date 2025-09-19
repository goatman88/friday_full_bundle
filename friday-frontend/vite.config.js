import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // Stop searching for external PostCSS config; use an empty one
  css: { postcss: { plugins: [] } },

  plugins: [react()],
  server:  { host: "0.0.0.0", port: 5173 },
  preview: { host: "0.0.0.0", port: 5173 },
});
