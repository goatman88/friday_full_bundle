import { defineConfig } from "vite";

// Lock PostCSS to nothing so Vite won't search for configs
export default defineConfig({
  build: { outDir: "dist" },
  css: { postcss: { plugins: [] } },
});


