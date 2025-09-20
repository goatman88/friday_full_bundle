// friday-frontend/vite.config.js
import { defineConfig } from "vite";

export default defineConfig({
  build: { outDir: "dist" },
  // Passing an object prevents Vite from searching for external PostCSS config
  css: { postcss: { plugins: [] } },
});

