import { defineConfig } from "vite";

// Minimal, no PostCSS, nothing fancy.
// Render will inject VITE_* at build time.
export default defineConfig({
  build: { outDir: "dist" }
});

