import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Minimal, no custom "define", no PostCSS config needed
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
});


