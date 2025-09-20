import { defineConfig } from "vite";
// Minimal, no "define", no external postcss files.
// Vite reads VITE_* at build time; use import.meta.env in code.
export default defineConfig({
  build: { outDir: "dist" },
  css: { postcss: { plugins: [] } }
});
